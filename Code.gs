/**
 * TV Podium Dashboard — Google Sheet Bound Apps Script Backend
 *
 * Returns compact dashboard JSON for the frontend.
 */

const APP_CONFIG = Object.freeze({
  HTML_FILE: 'Index',
  APP_TITLE: '🏆 ТОП-3 Продажи · ТВ',
  TIMEZONE: Session.getScriptTimeZone() || 'Asia/Tashkent',

  FACT_SHEET: 'Продажи по ТП (факт)',
  EMPLOYEE_SHEET: 'Сотрудники',

  PRODUCTS: ['AA', 'FA', 'FK', 'FS'],

  MAX_ROWS: 30000,
  MAX_COLS: 250,

  DATE_START_COL_INDEX: 5,

  FACT_COL_TYPE: 0,
  FACT_COL_PRODUCT: 2,
  FACT_COL_EMPLOYEE: 4,

  EMP_COL_NAME: 3,
  EMP_COL_CITY: 5,
  EMP_COL_REGION: 6,
});

function doGet() {
  return HtmlService
    .createHtmlOutputFromFile(APP_CONFIG.HTML_FILE)
    .setTitle(APP_CONFIG.APP_TITLE)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag(
      'viewport',
      'width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover'
    );
}

function getWebAppUrl_() {
  try {
    return ScriptApp.getService().getUrl() || '';
  } catch (err) {
    return '';
  }
}

function getDashboardData() {
  try {
    const lock = LockService.getScriptLock();
    lock.waitLock(15000);

    try {
      const ss = getSpreadsheet_();
      const factSheet = getRequiredSheet_(ss, APP_CONFIG.FACT_SHEET);
      const employeeSheet = getRequiredSheet_(ss, APP_CONFIG.EMPLOYEE_SHEET);

      validateSheetSize_(factSheet);
      validateSheetSize_(employeeSheet);

      const employeeMap = readEmployeeMap_(employeeSheet);
      return buildDashboardData_(factSheet, employeeMap, ss);
    } finally {
      try {
        lock.releaseLock();
      } catch (e) {}
    }
  } catch (err) {
    throw new Error(formatError_(err));
  }
}

function healthCheck() {
  try {
    const ss = getSpreadsheet_();
    const factSheet = getRequiredSheet_(ss, APP_CONFIG.FACT_SHEET);
    const employeeSheet = getRequiredSheet_(ss, APP_CONFIG.EMPLOYEE_SHEET);

    return {
      ok: true,
      spreadsheetName: ss.getName(),
      spreadsheetId: ss.getId(),
      factSheet: factSheet.getName(),
      employeeSheet: employeeSheet.getName(),
      timezone: APP_CONFIG.TIMEZONE,
      timestamp: new Date().toISOString(),
    };
  } catch (err) {
    return {
      ok: false,
      error: formatError_(err),
      timestamp: new Date().toISOString(),
    };
  }
}

function clearDashboardCache() {
  CacheService.getScriptCache().removeAll([]);
  return {
    ok: true,
    message: 'Cache clear requested',
    timestamp: new Date().toISOString(),
  };
}

function buildDashboardData_(factSheet, employeeMap, ss) {
  const values = factSheet
    .getRange(1, 1, factSheet.getLastRow(), factSheet.getLastColumn())
    .getValues();

  if (!values || values.length < 2) {
    return buildEmptyResponse_(ss, factSheet, employeeMap);
  }

  const header = values[0] || [];
  const dateMap = buildDateMap_(header);

  const years = Object.keys(dateMap)
    .map(Number)
    .sort(function (a, b) {
      return a - b;
    });

  if (!years.length) {
    throw new Error('Не найдены колонки с датами начиная с F.');
  }

  const out = {};

  years.forEach(function (year) {
    out[year] = {
      employeesByName: {},
    };
  });

  const productSet = {};
  APP_CONFIG.PRODUCTS.forEach(function (product) {
    productSet[product] = true;
  });

  for (let r = 1; r < values.length; r++) {
    const row = values[r];

    if (isEmptyRow_(row)) {
      continue;
    }

    const type = normalizeText_(row[APP_CONFIG.FACT_COL_TYPE]);
    if (type !== 'Месячный' && type !== 'Годовой') {
      continue;
    }

    const product = normalizeText_(row[APP_CONFIG.FACT_COL_PRODUCT]);
    if (!productSet[product]) {
      continue;
    }

    const employeeName = normalizeText_(row[APP_CONFIG.FACT_COL_EMPLOYEE]);
    if (!isValidEmployeeName_(employeeName)) {
      continue;
    }

    const employeeInfo = employeeMap[employeeName] || {
      city: '',
      region: '',
    };

    years.forEach(function (year) {
      const yearData = out[year];
      const monthToCol = dateMap[year];

      if (!yearData.employeesByName[employeeName]) {
        yearData.employeesByName[employeeName] = createEmployee_(employeeName, employeeInfo);
      }

      const employee = yearData.employeesByName[employeeName];

      if (!employee.prod_f[product]) {
        employee.prod_f[product] = createEmptyMonths_();
      }

      Object.keys(monthToCol).forEach(function (monthStr) {
        const month = Number(monthStr);
        const colIndex = monthToCol[month];
        const value = toSafeInteger_(row[colIndex]);

        if (value > 0) {
          employee.prod_f[product][month] += value;
        }
      });
    });
  }

  const compactData = {};

  years.forEach(function (year) {
    compactData[year] = {
      employees: Object.keys(out[year].employeesByName)
        .map(function (name) {
          return out[year].employeesByName[name];
        })
        .filter(function (employee) {
          return employeeHasSales_(employee);
        }),
    };
  });

  return {
    ok: true,
    products: APP_CONFIG.PRODUCTS,
    years: years,
    data: compactData,
    meta: {
      spreadsheetName: ss.getName(),
      factSheet: factSheet.getName(),
      employeeCount: Object.keys(employeeMap).length,
      generatedAt: new Date().toISOString(),
      timezone: APP_CONFIG.TIMEZONE,
        webAppUrl: getWebAppUrl_(),
        regionMap: employeeMap.__regions || {},
    },
  };
}

function readEmployeeMap_(sheet) {
  const values = sheet
    .getRange(1, 1, sheet.getLastRow(), sheet.getLastColumn())
    .getValues();

  const map = {};
  const regionMap = {}; // e.g. { R1: 'Toshkent' }
  const skip = /^(ИТОГО|Вакант|$)/i;

  for (let r = 1; r < values.length; r++) {
    const row = values[r];

    if (isEmptyRow_(row)) {
      continue;
    }

    const rawName = normalizeText_(row[APP_CONFIG.EMP_COL_NAME]);
    if (!rawName) {
      continue;
    }

    // Detect region header rows like "R1:" or "R1: RegionName"
    const regionHeaderMatch = rawName.match(/^R(\d+)\s*[:\-]?\s*(.*)$/i);

    if (regionHeaderMatch) {
      const code = ('R' + regionHeaderMatch[1]).toUpperCase();
      // Region name may be present inline after the code, or in the city/region columns
      const inline = regionHeaderMatch[2] ? regionHeaderMatch[2].trim() : '';
      const cityCell = normalizeText_(row[APP_CONFIG.EMP_COL_CITY]);
      const regionCell = normalizeText_(row[APP_CONFIG.EMP_COL_REGION]);
      const regionName = inline || cityCell || regionCell || '';

      if (regionName) {
        regionMap[code] = regionName;
      }

      // skip adding as an actual employee
      continue;
    }

    // Normal employee rows
    const name = rawName;
    if (!name || skip.test(name)) {
      continue;
    }

    map[name] = {
      city: normalizeText_(row[APP_CONFIG.EMP_COL_CITY]),
      region: normalizeText_(row[APP_CONFIG.EMP_COL_REGION]),
    };
  }

  // Replace any city/region codes like "R1" with the resolved region name from regionMap
  Object.keys(map).forEach(function (nm) {
    const entry = map[nm];
    if (entry.city && /^R\d+$/i.test(entry.city)) {
      const resolved = regionMap[entry.city.toUpperCase()];
      if (resolved) entry.city = resolved;
    }

    if (entry.region && /^R\d+$/i.test(entry.region)) {
      const resolved = regionMap[entry.region.toUpperCase()];
      if (resolved) entry.region = resolved;
    }
  });

  // expose region map for frontend diagnostics / fallback
  map.__regions = regionMap;

  return map;
}

function buildDateMap_(header) {
  const dateMap = {};

  for (let c = APP_CONFIG.DATE_START_COL_INDEX; c < header.length; c++) {
    const parsed = parseDateHeader_(header[c]);

    if (!parsed) {
      continue;
    }

    if (!dateMap[parsed.year]) {
      dateMap[parsed.year] = {};
    }

    dateMap[parsed.year][parsed.month] = c;
  }

  return dateMap;
}

function parseDateHeader_(value) {
  if (!value) {
    return null;
  }

  if (value instanceof Date) {
    return {
      year: value.getFullYear(),
      month: value.getMonth(),
    };
  }

  const s = String(value).trim();
  let m;

  m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) {
    return {
      year: Number(m[1]),
      month: Number(m[2]) - 1,
    };
  }

  m = s.match(/^(\d{4})[.\/](\d{1,2})[.\/](\d{1,2})/);
  if (m) {
    return {
      year: Number(m[1]),
      month: Number(m[2]) - 1,
    };
  }

  m = s.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (m) {
    return {
      year: Number(m[3]),
      month: Number(m[2]) - 1,
    };
  }

  m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) {
    return {
      year: Number(m[3]),
      month: Number(m[1]) - 1,
    };
  }

  const d = new Date(s);
  if (!isNaN(d.getTime()) && d.getFullYear() >= 2020 && d.getFullYear() <= 2035) {
    return {
      year: d.getFullYear(),
      month: d.getMonth(),
    };
  }

  return null;
}

function createEmployee_(name, info) {
  return {
    name: name,
    city: normalizeLocationValue_(info.city),
    region: normalizeLocationValue_(info.region),
    prod_f: {},
  };
}

function normalizeLocationValue_(value) {
  const text = normalizeText_(value);
  return text || '';
}

function createEmptyMonths_() {
  return [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
}

function employeeHasSales_(employee) {
  const products = Object.keys(employee.prod_f);

  for (let i = 0; i < products.length; i++) {
    const arr = employee.prod_f[products[i]] || [];

    for (let m = 0; m < arr.length; m++) {
      if (arr[m] > 0) {
        return true;
      }
    }
  }

  return false;
}

function buildEmptyResponse_(ss, factSheet, employeeMap) {
  return {
    ok: true,
    products: APP_CONFIG.PRODUCTS,
    years: [],
    data: {},
    meta: {
      spreadsheetName: ss.getName(),
      factSheet: factSheet.getName(),
      employeeCount: Object.keys(employeeMap).length,
      generatedAt: new Date().toISOString(),
      timezone: APP_CONFIG.TIMEZONE,
      webAppUrl: getWebAppUrl_(),
      regionMap: (employeeMap && employeeMap.__regions) || {},
    },
  };
}

function getSpreadsheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  if (!ss) {
    throw new Error('Active spreadsheet is not available. Make sure this script is bound to Google Sheet.');
  }

  return ss;
}

function getRequiredSheet_(ss, sheetName) {
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    throw new Error('Sheet not found: "' + sheetName + '"');
  }

  return sheet;
}

function validateSheetSize_(sheet) {
  const rows = sheet.getLastRow();
  const cols = sheet.getLastColumn();

  if (rows > APP_CONFIG.MAX_ROWS) {
    throw new Error(
      'Sheet "' + sheet.getName() + '" has too many rows: ' +
      rows + '. Limit: ' + APP_CONFIG.MAX_ROWS
    );
  }

  if (cols > APP_CONFIG.MAX_COLS) {
    throw new Error(
      'Sheet "' + sheet.getName() + '" has too many columns: ' +
      cols + '. Limit: ' + APP_CONFIG.MAX_COLS
    );
  }
}

function normalizeText_(value) {
  if (value === null || value === undefined) {
    return '';
  }

  if (value instanceof Date) {
    return Utilities.formatDate(value, APP_CONFIG.TIMEZONE, 'yyyy-MM-dd');
  }

  return String(value).trim();
}

function toSafeInteger_(value) {
  if (value === null || value === undefined || value === '') {
    return 0;
  }

  const number = Number(value);

  if (!isFinite(number)) {
    return 0;
  }

  return Math.round(number);
}

function isValidEmployeeName_(name) {
  if (!name) {
    return false;
  }

  if (name === 'Сотрудник' || name === 'Для формулы' || name === 'ИТОГО') {
    return false;
  }

  // Exclude region header tokens like R1, R2, R10, with optional trailing ':' or '-'
  if (/^(R\d+\s*[:\-]?\s*|Вакант)$/i.test(name)) {
    return false;
  }

  return true;
}

function isEmptyRow_(rowValues) {
  for (let i = 0; i < rowValues.length; i++) {
    const value = rowValues[i];

    if (value !== null && value !== '' && value !== undefined) {
      return false;
    }
  }

  return true;
}

function formatError_(err) {
  if (!err) {
    return 'Unknown error';
  }

  const msg = err.message ? String(err.message) : String(err);

  return msg
    .replace(/Exception:\s*/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

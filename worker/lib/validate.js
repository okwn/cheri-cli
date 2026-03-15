import { HttpError } from "./http.js";

function hasControlCharacters(value) {
  return /[\u0000-\u001f\u007f]/.test(value);
}

export function requiredString(value, fieldName, options = {}) {
  const {
    minLength = 1,
    maxLength = 256,
    pattern = null,
    normalize = (input) => String(input).trim(),
  } = options;
  const normalized = normalize(value ?? "");
  if (!normalized) {
    throw new HttpError(400, `${fieldName} is required.`);
  }
  if (normalized.length < minLength || normalized.length > maxLength) {
    throw new HttpError(400, `${fieldName} must be ${minLength}-${maxLength} characters.`);
  }
  if (hasControlCharacters(normalized)) {
    throw new HttpError(400, `${fieldName} contains invalid characters.`);
  }
  if (pattern && !pattern.test(normalized)) {
    throw new HttpError(400, `${fieldName} is invalid.`);
  }
  return normalized;
}

export function optionalString(value, fieldName, options = {}) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return "";
  }
  return requiredString(value, fieldName, { minLength: 0, ...options });
}

export function booleanFlag(value, defaultValue = false) {
  if (value === undefined || value === null) {
    return defaultValue;
  }
  return !!value;
}

export function objectValue(value, fieldName) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(400, `${fieldName} must be an object.`);
  }
  return value;
}

export function nonNegativeNumber(value, fieldName, { integer = false, max = Number.MAX_SAFE_INTEGER } = {}) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0 || number > max) {
    throw new HttpError(400, `${fieldName} must be a non-negative number.`);
  }
  if (integer && !Number.isInteger(number)) {
    throw new HttpError(400, `${fieldName} must be an integer.`);
  }
  return number;
}

export function inviteCode(value) {
  return requiredString(value, "invite_code", {
    minLength: 12,
    maxLength: 32,
    pattern: /^CHR-TEAM-[A-Z2-9]{8}$/,
  });
}

export function workspaceName(value) {
  return requiredString(value, "Workspace name", {
    minLength: 2,
    maxLength: 80,
    normalize: (input) => String(input || "").trim().replace(/\s+/g, " "),
  });
}

export function safeLabel(value, fieldName = "Label", maxLength = 80) {
  return optionalString(value, fieldName, { minLength: 0, maxLength });
}

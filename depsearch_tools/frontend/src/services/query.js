import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const TAB_ID_KEY = "tab_id";

function getTabId() {
  let tabId = sessionStorage.getItem(TAB_ID_KEY);
  if (!tabId) {
    tabId = crypto.randomUUID();
    sessionStorage.setItem(TAB_ID_KEY, tabId);
  }
  return tabId;
}

export async function basicQuery({ corpus, query, contextSize, signal }) {
  const tabId = getTabId();
  try {
    const response = await axios.post(`${API_URL}/basic-query`, {
      corpus,
      query,
      context_size: contextSize,
      id: tabId,
    }, { signal });
    return response.data.sentences;
  } catch (error) {
    if (axios.isCancel(error)) {
      throw error;
    }
    const message =
      error.response?.data?.detail ||
      'An unexpected error occurred while handling the basic query.';
    console.error('Basic query failed:', message);
    throw new Error(message);
  }
}

export async function stringQuery({ corpus, query, searchBy, contextSize, signal }) {
  const tabId = getTabId();
  try {
    const response = await axios.post(`${API_URL}/string-query`, {
      corpus,
      query,
      search_by: searchBy,
      context_size: contextSize,
      id: tabId,
    }, { signal });
    return response.data.sentences;
  } catch (error) {
    if (axios.isCancel(error)) {
      throw error;
    }
    const message =
      error.response?.data?.detail ||
      'An unexpected error occurred while handling the string query.';
    console.error('String query failed:', message);
    throw new Error(message);
  }
}

export async function advancedQuery({ corpus, query, contextSize, signal }) {
  const tabId = getTabId();
  try {
    const response = await axios.post(`${API_URL}/advanced-query`, {
      corpus,
      query,
      context_size: contextSize,
      id: tabId,
    }, { signal });
    return response.data.output;
  } catch (error) {
    if (axios.isCancel(error)) {
      throw error;
    }
    const message =
      error.response?.data?.detail ||
      'An unexpected error occurred while handling the advanced query.';
    console.error('Advanced query failed:', message);
    throw new Error(message);
  }
}

export async function cancelQuery() {
  const tabId = getTabId();
  try {
    await axios.post(`${API_URL}/cancel-query`, { id: tabId });
  } catch (error) {
    console.error('Failed to cancel query:', error);
  }
}

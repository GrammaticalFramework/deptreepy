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

export async function parseDependencies({ text, language }) {
  const tabID = getTabId();
  try {
    const response = await axios.post(
      `${API_URL}/dependency-parsing`, 
      {
        text,
        language,
        id: tabID,
      },
      {
        headers: {
          'Content-Type': 'application/json',
        },
        responseType: 'text', // Ensure raw HTML string is returned
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error parsing dependencies:', error);
    throw error;
  }
}
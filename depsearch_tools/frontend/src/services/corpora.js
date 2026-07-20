import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export async function getCorpusList() {
  try {
    const response = await axios.get(
      `${API_URL}/corpora`, 
    );
    return response.data.corpora;
  } catch (error) {
    console.error('Error getting corpus list:', error);
    throw error;
  }
}
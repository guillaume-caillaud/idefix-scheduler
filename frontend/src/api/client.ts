import axios from 'axios';

// En production: /api (proxy nginx → FastAPI)
// En dev: /api (proxy Vite → localhost:8000)
// Peut être surchargé via VITE_API_BASE=http://localhost:8000
const baseURL = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';

const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;

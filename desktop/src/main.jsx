import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Sin StrictMode: en dev, StrictMode monta/desmonta/remonta los componentes,
// creando DOS WebSocket connections brevemente. Eso causa que eventos como
// 'transcribed' lleguen por ambos y el chat muestre mensajes duplicados.
// En produccion StrictMode no tiene efecto, asi que quitarlo es seguro.
createRoot(document.getElementById('root')).render(<App />)

import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [apiStatus, setApiStatus] = useState(null)

  // Sprawdzenie statusu API przy pierwszym ładowaniu
  useEffect(() => {
    const checkApiStatus = async () => {
      try {
        const apiUrl =
          process.env.NODE_ENV === 'production'
            ? '/api/status'
            : 'http://localhost:3000/api/status'
        const response = await fetch(apiUrl)
        if (response.ok) {
          const data = await response.json()
          setApiStatus(data)
          console.log('Status API:', data)
        }
      } catch (error) {
        console.error('Błąd podczas sprawdzania statusu API:', error)
      }
    }

    checkApiStatus()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!input.trim()) return

    // Dodaj wiadomość użytkownika do historii
    const userMessage = { role: 'user', content: input }
    setMessages([...messages, userMessage])
    setInput('')
    setLoading(true)

    try {
      // URL do API
      const apiUrl =
        process.env.NODE_ENV === 'production'
          ? '/api'
          : 'http://localhost:3000/api'

      console.log('Wysyłanie zapytania do:', apiUrl)

      // Wykonaj zapytanie do API
      const startTime = performance.now()
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: input }),
      })
      const requestTime = performance.now() - startTime

      // Logowanie odpowiedzi
      console.log('Status odpowiedzi:', response.status)
      console.log('Nagłówki odpowiedzi:', response.headers)

      const responseText = await response.text()
      console.log('Surowa odpowiedź:', responseText)

      let data
      try {
        data = JSON.parse(responseText)
      } catch (parseError) {
        console.error('Błąd parsowania JSON:', parseError)
        throw new Error(`Otrzymano nieprawidłową odpowiedź: ${responseText}`)
      }

      console.log('Odpowiedź API:', data)

      // Dodaj odpowiedź od API do historii
      const botMessage = {
        role: 'assistant',
        content:
          data.answer ||
          'Przepraszam, nie mogę znaleźć odpowiedzi na to pytanie.',
        sources: data.sources || [],
        stats: data.stats || {
          requestTime: `${(requestTime / 1000).toFixed(2)}s`,
        },
        fromCache: data.from_cache || false,
        requestId: data.request_id || 'unknown',
      }

      setMessages((prevMessages) => [...prevMessages, botMessage])
    } catch (error) {
      console.error('Błąd:', error)
      // Dodaj wiadomość o błędzie z pełnymi szczegółami
      const errorMessage = {
        role: 'assistant',
        content: `Przepraszam, wystąpił błąd podczas przetwarzania zapytania: ${error.message}`,
      }
      setMessages((prevMessages) => [...prevMessages, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>Claro - Asystent prawny</h1>
        {apiStatus && (
          <div className="api-status">
            <span
              className={`status-indicator ${
                apiStatus.database?.status === 'online' ? 'online' : 'offline'
              }`}
            ></span>
            <span className="status-text">
              {apiStatus.database?.status === 'online'
                ? `Baza danych: online (${
                    apiStatus.database?.articles || '?'
                  } artykułów)`
                : 'Baza danych: offline'}
            </span>
          </div>
        )}
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-message">
            <h2>Witaj w Claro!</h2>
            <p>
              Zadaj pytanie dotyczące prawa podatkowego, a ja spróbuję na nie
              odpowiedzieć na podstawie dostępnych przepisów prawnych.
            </p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-content">{message.content}</div>
              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <h4>Źródła:</h4>
                  <ul>
                    {message.sources.map((source, idx) => (
                      <li key={idx}>{source}</li>
                    ))}
                  </ul>
                </div>
              )}
              {message.stats && message.role === 'assistant' && (
                <div className="message-stats">
                  {message.fromCache ? (
                    <span className="cache-info">
                      ⚡ Z pamięci podręcznej ({message.stats.cache_age}s)
                    </span>
                  ) : (
                    <>
                      <span className="time-info">
                        Czas wyszukiwania:{' '}
                        {message.stats.search_time || message.stats.requestTime}
                      </span>
                      {message.stats.openai_time && (
                        <span className="time-info">
                          Czas odpowiedzi AI: {message.stats.openai_time}
                        </span>
                      )}
                    </>
                  )}
                  {message.requestId && (
                    <span className="request-id">ID: {message.requestId}</span>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="message assistant loading">
            <div className="loading-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Wpisz swoje pytanie prawne..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? 'Szukam...' : 'Wyślij'}
        </button>
      </form>
    </div>
  )
}

export default App

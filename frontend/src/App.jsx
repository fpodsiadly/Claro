import { useState } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

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
          : 'http://localhost:3000/api' // Dla lokalnego rozwoju

      console.log('Wysyłanie zapytania do:', apiUrl)

      // Wykonaj zapytanie do API
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: input }),
      })

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
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-message">
            <h2>Witaj w Claro!</h2>
            <p>
              Zadaj pytanie dotyczące prawa podatkowego, a ja spróbuję na nie
              odpowiedzieć.
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
          placeholder="Wpisz swoje pytanie..."
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

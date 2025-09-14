import React, { useState, useEffect, useRef } from 'react';
import ContentstackAppSDK from '@contentstack/app-sdk';
import AnalyticsDashboard from './AnalyticsDashboard';
import './App.css';

// Replace this with your actual Vercel deployment URL
const API_BASE_URL = 'https://techsurf-2k25-git-feature-development-sujals-projects-9af316d2.vercel.app';

function App() {
  // SDK State
  const [appSdk, setAppSdk] = useState(null);
  const [view, setView] = useState('search'); // 'search' or 'analytics'

  // Application State
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState([]);
  const [smartSnippet, setSmartSnippet] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedLocale] = useState('');
  const [selectedContentType] = useState('');
  const [threshold, setThreshold] = useState(35);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  // Initialize the Contentstack App SDK
  useEffect(() => {
    ContentstackAppSDK.init().then(setAppSdk);
  }, []);

  // --- API Call Functions ---

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    setResults([]);
    setSmartSnippet('');
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          locale: selectedLocale || null,
          content_type: selectedContentType || null,
          threshold: threshold,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);
      setSmartSnippet(data.smart_snippet || '');

      if (!data.results || data.results.length === 0) {
        setError('No results found. Try a different search term.');
      }
    } catch (error) {
      console.error("Error fetching search results:", error);
      setError('Failed to fetch search results. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFindSimilar = async (id, title) => {
    if (!id) return;

    setIsLoading(true);
    setResults([]);
    setSmartSnippet('');
    setError('');
    setSearchQuery(`Finding content similar to "${title}"...`);

    try {
      const response = await fetch(`${API_BASE_URL}/find_similar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);

      if (!data.results || data.results.length === 0) {
        setError('No similar content found.');
      }
    } catch (error) {
      console.error("Error fetching similar results:", error);
      setError('Failed to fetch similar content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      mediaRecorder.current.stop();
      setIsRecording(false);
    } else {
      // Start recording
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder.current = new MediaRecorder(stream);
        audioChunks.current = [];

        mediaRecorder.current.ondataavailable = (event) => {
          audioChunks.current.push(event.data);
        };

        mediaRecorder.current.onstop = async () => {
          const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });
          await sendAudioToServer(audioBlob);
          // Stop all tracks on the stream to turn off the mic indicator
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.current.start();
        setIsRecording(true);
      } catch (err) {
        console.error("Error accessing microphone:", err);
        setError("Microphone access was denied. Please allow microphone access in your browser settings.");
      }
    }
  };

  const sendAudioToServer = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/voice-search`, {
        method: 'POST',
        body: formData, // NOTE: Do NOT set Content-Type header, browser does it for you
      });

      if (!response.ok) {
        throw new Error('Failed to transcribe audio.');
      }

      const data = await response.json();
      setSearchQuery(data.transcript); // Put the text in the search bar

    } catch (error) {
      console.error("Error transcribing audio:", error);
      setError('Failed to transcribe audio. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // --- Render ---

  if (!appSdk) {
    return <div className="Loading">Loading Contentstack App...</div>;
  }

  return (
    <div className="AppContainer">
      {/* --- NEW: Navigation Toggle --- */}
      <div className="NavContainer">
        <button
          className={`NavButton ${view === 'search' ? 'active' : ''}`}
          onClick={() => setView('search')}
        >
          Search
        </button>
        <button
          className={`NavButton ${view === 'analytics' ? 'active' : ''}`}
          onClick={() => setView('analytics')}
        >
          Analytics
        </button>
      </div>

      {/* --- Conditional Rendering --- */}
      {view === 'search' ? (
        <>
          <div className="Header">
            <h2>🔍 Semantic Search</h2>
            <p>Search through your content intelligently</p>
          </div>

          <div className="SearchContainer">
            <input
              type="text"
              className="SearchInput"
              placeholder="Search for content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button
              className={`MicButton ${isRecording ? 'recording' : ''}`}
              onClick={handleToggleRecording}
            >🎤</button>
            <button className="SearchButton" onClick={handleSearch} disabled={isLoading}>
              {isLoading ? 'Searching...' : 'Search'}
            </button>
          </div>

          <div className="FilterContainer">
            <label htmlFor="threshold">Relevance Threshold: <strong>{threshold}%</strong></label>
            <input
              type="range"
              id="threshold"
              min="10"
              max="90"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="ThresholdSlider"
            />
          </div>

          <div className="ResultsContainer">
            {isLoading && (
              <div className="SpinnerContainer">
                <div className="Spinner"></div>
              </div>
            )}

            {error && (
              <div className="ErrorMessage">
                <p>⚠️ {error}</p>
              </div>
            )}

            {smartSnippet && (
              <div className="SmartSnippet">
                <p className="SnippetHeader">✨ Smart Answer</p>
                <p>{smartSnippet}</p>
              </div>
            )}

            {results.map((result, index) => (
              <div key={result.id || index} className="ResultCard">
                <div className="ResultContent">
                  <p className="ResultTitle">{result.metadata?.title || 'Untitled Content'}</p>
                  <p className="ResultInfo">
                    Score: {(result.score * 100).toFixed(2)}% | Type: {result.metadata?.content_type || 'Unknown'}
                  </p>
                  {result.metadata?.description && (
                    <p className="ResultDescription">{result.metadata.description}</p>
                  )}
                </div>
                <button
                  className="SimilarButton"
                  onClick={() => handleFindSimilar(result.id, result.metadata.title)}
                  title="Find similar content"
                >
                  🪄
                </button>
              </div>
            ))}

            {!isLoading && results.length === 0 && !smartSnippet && !error && (
              <div className="Placeholder">
                <p>!! Your search results will appear here !!</p>
                <p>Try searching for content in your knowledge base!</p>
              </div>
            )}
          </div>
        </>
      ) : (
        <AnalyticsDashboard apiBaseUrl={API_BASE_URL} />
      )}
    </div>
  );
}

export default App;
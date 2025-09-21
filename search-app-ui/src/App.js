import React, { useState, useEffect, useRef } from 'react';
import ContentstackAppSDK from '@contentstack/app-sdk';
import AnalyticsDashboard from './AnalyticsDashboard';
import './App.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faThumbsUp, faThumbsDown, faMicrophone } from '@fortawesome/free-solid-svg-icons';

// VERCEL DEPLOYMENT URL
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://techsurf-2k25.vercel.app';

function App() {
  // SDK State
  const [appSdk, setAppSdk] = useState(null);
  const [view, setView] = useState('search');

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
  const [feedbackState, setFeedbackState] = useState({});
  const [loadingMessage, setLoadingMessage] = useState('');

  // Initialize the Contentstack App SDK
  // useEffect(() => {
  //   // Only initialize if running inside a parent window (the iframe)
  //   if (window.parent) {
  //     ContentstackAppSDK.init().then(setAppSdk);
  //   }
  // }, []);

  useEffect(() => {
    // Check if the app is running standalone (not in an iframe)
    const isStandalone = window.self === window.top;

    if (isStandalone) {
      // If running by itself, we don't need the SDK.
      // Set a dummy object to bypass the loading screen and render the app.
      setAppSdk({});
    } else {
      // If running inside Contentstack, initialize the SDK as normal.
      ContentstackAppSDK.init().then(setAppSdk);
    }
  }, []);

  // --- API Call Functions ---

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoadingMessage('');
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
    setLoadingMessage(`Finding content similar to "${title}"...`);


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
      setLoadingMessage(''); // Clear the message when done
    }
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      //Stop recording
      mediaRecorder.current.stop();
      setIsRecording(false);
    } else {
      //Start recording
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
          //Stop all tracks on the stream to turn off the mic indicator
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

  //Send audio to the server!!

  const sendAudioToServer = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/voice-search`, {
        method: 'POST',
        body: formData,
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

  const handleFeedback = async (resultId, feedbackType) => {
    // Check the current feedback for this result
    const currentFeedback = feedbackState[resultId];
    // If the user clicks the same button again, we'll deselect it (set to null)
    const newFeedback = currentFeedback === feedbackType ? null : feedbackType;

    // Update the UI immediately for a responsive feel
    setFeedbackState(prevState => ({
      ...prevState,
      [resultId]: newFeedback
    }));

    try {
      // Send the feedback to the server
      await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          result_id: resultId,
          feedback_type: newFeedback,
        }),
      });
    } catch (error) {
      console.error("Error submitting feedback:", error);
      // If the API call fails, revert the button to its original state
      setFeedbackState(prevState => ({
        ...prevState,
        [resultId]: currentFeedback
      }));
    }
  };

  // !---! Render !---!

  if (!appSdk) {
    return <div className="Loading">Loading Contentstack App...</div>;
  }

  return (
    <div className="AppContainer">
      {/* --- Navigation Toggle --- */}
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
            <h2>🔍 Semantic Similarity Search</h2>
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
              title={isRecording ? 'Stop recording' : 'Start recording'}
            >
              <FontAwesomeIcon icon={faMicrophone} />
            </button>
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

            {/*Display the loading message */}
            {isLoading && loadingMessage && (
              <div className="LoadingMessage">{loadingMessage}</div>
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
              <a
                href={result.metadata.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ResultCardLink"
                key={result.id || index}
              >
                <div className="ResultCard">
                  <div className="ResultContent">
                    <p className="ResultTitle">{result.metadata?.title || 'Untitled Content'}</p>
                    <p className="ResultInfo">
                      Score: {(result.score * 100).toFixed(2)}% | Type: {result.metadata?.content_type || 'Unknown'}
                    </p>
                    {result.metadata?.description && (
                      <p className="ResultDescription">{result.metadata.description}</p>
                    )}
                  </div>
                  <div className="ActionButtonsContainer">
                    <button
                      className={`FeedbackButton ${feedbackState[result.id] === 'like' ? 'liked' : ''}`}
                      onClick={(e) => { e.preventDefault(); handleFeedback(result.id, 'like'); }}
                      title="Like result"
                    >
                      <FontAwesomeIcon icon={faThumbsUp} />
                    </button>
                    <button
                      className={`FeedbackButton ${feedbackState[result.id] === 'dislike' ? 'disliked' : ''}`}
                      onClick={(e) => { e.preventDefault(); handleFeedback(result.id, 'dislike'); }}
                      title="Dislike result"
                    >
                      <FontAwesomeIcon icon={faThumbsDown} />
                    </button>
                    <button
                      className="SimilarButton"
                      onClick={(e) => { e.preventDefault(); handleFindSimilar(result.id, result.metadata.title); }}
                      title="Find similar content"
                    >
                      🪄
                    </button>
                  </div>
                </div>
              </a>
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

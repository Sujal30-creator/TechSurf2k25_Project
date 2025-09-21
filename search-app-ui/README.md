This `README` is more focused on the React application itself.

```markdown
# Semantic Search UI

This is the React-based frontend for the TechSurf 2k25 Semantic Search project. It provides a user-friendly interface for interacting with the AI-powered search backend and is designed to be embedded as a custom application within the Contentstack dashboard.

---

## Features

- **Modern Search Interface:** A clean and responsive UI for entering search queries.
- **Interactive Results:** Search results are displayed in clear cards, which are clickable and link directly to the Contentstack entry.
- **User Feedback:** Like/Dislike buttons on each result card with interactive visual feedback.
- **Find Similar:** A one-click option on each result to discover other contextually similar content.
- **Voice Input:** A microphone button allows for hands-free, speech-to-text searching.
- **Analytics Dashboard:** A dedicated view with multiple charts and lists to visualize search data, content gaps, and user feedback.

---

## Tech Stack

- **React.js:** For building the user interface.
- **Chart.js:** For creating the data visualizations on the analytics dashboard.
- **Font Awesome:** For a clean and professional icon set.
- **Contentstack App SDK:** For integration with the Contentstack UI.

---

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in development mode.<br />
Open [https://localhost:3000](https://localhost:3000) to view it in the browser.

The page will reload if you make edits.

### `npm run build`

Builds the app for production to the `build` folder.<br />
It correctly bundles React in production mode and optimizes the build for the best performance.

### `Configuration`
To run this application, you need to have the backend server running. The frontend will make API calls to the URL specified in the `API_BASE_URL` constant in `src/App.js`. For local development, this should point to your local backend server (e.g., `http://localhost:8000`). For production, it points to the deployed Vercel URL.

# TechSurf 2k25 - AI Powered Semantic Search for ContentStack


"AI has always been an interesting topic for me" this is the statement which you might have heard from any computer science grad. and that's the reason I speak it too, one might call it a `Community Pressure` but seriously I don't `;)`. To learn about AI, RAG, MCP, Vector DB and all the other fancy words you might can think around it I got a chance to learn those in this journey of Techsurf 2025.

Techsurf is an national level hackathon hosted on https://www.edquest.pro by Contentstack. The journey for this hackathon began in mid August where we were instructed to complete a course on their platform which was named as `ContentStack 101 Developer`. Most of my colleagues joined techsurf initially but found this course a bit boring and I too. But that's what developers do, they should learn how to read documents and how to analyze it. So I completed the course and successfully entered for Round-2. We were given 4 Problem Statements among which we were needed to choose one and create the required solution for it. The Contentstack team designed such Problem statements which they are facing currently which means that the solutions for these P.S's are solving real-life issues. This is where the statement told to me by my professor during the initial day of my college clicked in my mind!! which was :- "Engineers solves Real world problems which help others and make their life simple". So this "Iron Man" moment I never wanted to miss and I started learning from the resources provided by the team.
Btw here's the link to p.s. :- https://eu-assets.contentstack.com/v3/assets/bltf7ed5a6bb86457f5/bltb44f922984de6c7c/68b7aa4efc395130d6f038cb/Problem_Statements_2025.pdf

---

### Why did I choose this Problem Statement?

As I mentioned earlier that this was the moment I was waiting for now it was the time to choose one problem statement. Among all the 4 I found that p.s 2 is doable and while going through the resources provided by the team `Vector Embeddings` and `Vector Databases` were new but a bit interesting for me and speaking frankly the fancy terms used in the p.s made me think that less student's might go for this and which will help me to enter in a less populated P.S , but on a later stage this logic was proved wrong `:(`

---

### The journey of creating the solution

Round-2 started on 3rd of September but till 5th I was still deciding and learning about the p.s. and then realized that I have wasted a lot of time just deciding the plan and the work I should assign for each day. The submission dates were on 16th and had only 10 days remaining with me, I divided my each day with the work I would perform of completing this project. I decided to use the technologies which I have used earlier. So here are they:-

## TechStack:
- **Backend:**
  - **Framework:** Python, FastAPI
  - **AI & Embeddings:** OpenAI API (text-embedding-3-small, GPT-3.5-Turbo, Whisper) `I also bought OpenAI credits for 5.99$ for better performance :(`
  - **Vector Database:** Pinecone
  - **Analytics & Caching:** Redis (Vercel KV)
- **Frontend:**
  - **Framework:** React.js
  - **Charting:** Chart.js with `react-chartjs-2`
  - **Styling:** CSS
  - **Icons:** Font Awesome
- **Deployment:**
  - Vercel (for both frontend and serverless backend)


I built my backend within 2 days and my frontend within 3 days and my project was ready on 10th of September !!Hurrah!!. But this alone wasn't sufficient to win the competition here is where I started thinking about some features I could add into it. It was a bit difficult because what features can you add for a search bar?!! I implemented some and later asked my friends like What all they miss in a searchbar ? Got some insights from it and started implementing them too!! Before 16 my project was ready where I built the search application as the p.s. demanded and an analytics page as well!! I tried to implement an feature where user's do not need to type a content rather they can use a `Speech-to-text` feature. It failed and I was bit confused about the error too!! Thankfully the team extended the dates and later was helped by the team about the error. It was an `Permission Policy Violation Error` where I wasn't able to use the microphone as I was rendering my app inside an iframe in Contentstack. You can use the feature if you run the script on your browser but `remember not inside an iframe!!`. Atlast, the feature I implemented are :-

## Features

- **Semantic Search:** Utilizes OpenAI's `text-embedding-3-small` model to understand the contextual meaning of search queries, not just keywords.
- **Find Similar Content:** Users can find other relevant entries based on the content of a specific search result.
- **Voice-to-Text Search:** A modern, accessible way for users to perform searches by speaking directly into their microphone, powered by OpenAI's Whisper model.
- **Adjustable Relevance Threshold:** A slider allows power-users to fine-tune the sensitivity of the search results.
- **User Feedback System:** Like/Dislike buttons on each result provide a feedback loop to gauge content effectiveness.
- **Comprehensive Analytics Dashboard:**
  - **Search Effectiveness Chart:** A pie chart visualizing the ratio of successful searches to "content gaps" (searches with no results).
  - **Most Liked/Disliked Content:** Bar charts displaying the top-rated and lowest-rated content based on user feedback.
  - **Top Searches & Content Gaps:** Lists that show what users are searching for most and where the knowledge base is lacking.

---

The journey was amazing and I was able to learn and implement new things, I know I'm acting like an ideal student... but it's a fact anyways!! Learning about CMS to actually building an project using it and it's features was something I never knew I could do it. Contentstack has always been my aim as I everyday watch the company's office by standing beneath it, only because the Virar office is on top of a building which is adjacent to my residence `;)`. But it was always my dream which I see it from open eyes and got a chance to showcase my skills through this hackathon!!



## Local Setup and Installation

To run this project on your local machine, you will need two terminals.

### Prerequisites
- Python 3.9+ and Pip
- Node.js and npm
- Git

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd Techsurf-2k25
```


### Backend Setup (Terminal 1)

1. To create and activate a venv(virtual env.) ---> ```python -m venv venv``` (source venv/bin/activate  # On Windows: venv\Scripts\activate)

2. Install Python dependencies ---> ```pip install -r requirements.txt```

3. Create a `.env` file in the root directory and add your API keys: 
    OPENAI_API_KEY="sk-..."
    PINECONE_API_KEY="..."
    PINECONE_INDEX_NAME="..."
    KV_URL="redis://..."
    CONTENTSTACK_API_KEY="..."
    CONTENTSTACK_MANAGEMENT_TOKEN="..."

4. Start the backend server ---> ```uvicorn main:app --reload``` (This will run at ```http://127.0.0.1:8000```)

### Frontend Setup (Terminal 2)

1. Navigate to the UI directory ---> ```cd search-app-ui```
2. Install JS dependencies ---> ```npm install```
3. Create a .env file in the search-app-ui directory for local development ---> ```HTTPS=true```
4. Start the frontend server ---> ```npm start``` (inside the src folder so perform ```cd src``` before that!! The app will then open at ```https://localhost:3000```)


### Btw here are some important links:

Vercel Backend URL :- ```https://techsurf-2k25.vercel.app/```
Contentstack launch URL :- ```search-app-ui-feature-development.eu-contentstackapps.com```

Youtube Video Link :- ```https://youtu.be/eX8Vtq_HyHQ```
Google Slides link :- ```https://docs.google.com/presentation/d/16vPDMBdoR1Byo8EaxQTBd-xJuLwka64yHpqLRJsFgM0/edit?usp=sharing```






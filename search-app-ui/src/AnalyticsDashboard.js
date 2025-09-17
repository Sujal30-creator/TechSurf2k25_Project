import React, { useState, useEffect } from 'react';
import { Pie, Bar } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

function AnalyticsDashboard({ apiBaseUrl }) {
    const [topSearches, setTopSearches] = useState([]);
    const [contentGaps, setContentGaps] = useState([]);
    // A separate state to hold the data for our summary chart.
    const [summaryData, setSummaryData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [feedbackData, setFeedbackData] = useState({ most_liked: [], most_disliked: [] });

    useEffect(() => {
        const fetchAnalyticsLists = async () => {
            try {
                const response = await fetch(`${apiBaseUrl}/analytics`);
                const data = await response.json();
                setTopSearches(data.top_searches || []);
                setContentGaps(data.content_gaps || []);
            } catch (error) {
                console.error("Failed to fetch analytics lists:", error);
            }
        };

        // fetches the summary data for the pie chart.
        const fetchAnalyticsSummary = async () => {
            try {
                const response = await fetch(`${apiBaseUrl}/analytics/summary`);
                const data = await response.json();
                setSummaryData(data);
            } catch (error) {
                console.error("Failed to fetch analytics summary:", error);
            }
        };

        //fetches the feedback data for the graph
        const fetchFeedbackAnalytics = async () => {
            try {
                const response = await fetch(`${apiBaseUrl}/analytics/feedback`);
                const data = await response.json();
                setFeedbackData(data);
            } catch (error) {
                console.error("Failed to fetch feedback analytics:", error);
            }
        };

        const loadAllData = async () => {
            setIsLoading(true);
            // Run both API calls at the same time.
            await Promise.all([fetchAnalyticsLists(), fetchAnalyticsSummary(), fetchFeedbackAnalytics()]);
            setIsLoading(false);
        };



        loadAllData();
    }, [apiBaseUrl]);

    const pieChartData = {
        labels: ['Successful Searches', 'Content Gaps'],
        datasets: [
            {
                label: '# of Searches',
                data: summaryData
                    ? [summaryData.total_searches - summaryData.content_gaps, summaryData.content_gaps]
                    : [0, 0],
                backgroundColor: [
                    'rgba(75, 192, 192, 0.6)', // Green color for success
                    'rgba(255, 99, 132, 0.6)',  // Red color for gaps
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 99, 132, 1)',
                ],
                borderWidth: 1,
            },
        ],
    };

    const likedChartData = {
        labels: feedbackData.most_liked.map(item => item.title),
        datasets: [{
            label: 'Likes',
            data: feedbackData.most_liked.map(item => item.likes),
            backgroundColor: 'rgba(75, 192, 192, 0.6)',
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1
        }]
    };

    const dislikedChartData = {
        labels: feedbackData.most_disliked.map(item => item.title),
        datasets: [{
            label: 'Dislikes',
            data: feedbackData.most_disliked.map(item => item.dislikes),
            backgroundColor: 'rgba(255, 99, 132, 0.6)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1
        }]
    };

    const barChartOptions = {
        indexAxis: 'y', // This makes the bar chart horizontal
        responsive: true,
        plugins: {
            legend: { display: false },
            title: { display: true, text: 'Content Performance' }
        }
    };

    if (isLoading) {
        return (
            <div className="SpinnerContainer">
                <div className="Spinner"></div>
            </div>
        );
    }

    return (
        <div className="AnalyticsContainer">
            <div className="AnalyticsColumn">
                <h3 className="AnalyticsHeader">Search Effectiveness</h3>
                {/* limit the height to keep it from getting too large. */}
                <div style={{ height: '300px', position: 'relative' }}>
                    <Pie data={pieChartData} options={{ maintainAspectRatio: false, responsive: true }} />
                </div>
            </div>

            <div className="AnalyticsColumn">
                <h3 className="AnalyticsHeader">Top Searches</h3>
                <ul className="AnalyticsList">
                    {topSearches.map((item, index) => (
                        <li key={index} className="AnalyticsListItem">
                            <span>{item.query}</span>
                            <span className="AnalyticsCount">{item.count}</span>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="AnalyticsColumn">
                <h3 className="AnalyticsHeader">Content Gaps</h3>
                <ul className="AnalyticsList">
                    {contentGaps.map((item, index) => (
                        <li key={index} className="AnalyticsListItem">
                            <span>{item.query}</span>
                            <span className="AnalyticsCount">{item.count}</span>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="AnalyticsPageContainer"> // Use a new container class
                <div className="AnalyticsRow"> // Wrap first row in a div
                    {/* ... Your Pie Chart and List columns ... */}
                </div>
                <div className="AnalyticsRow"> // Second row for the new charts
                    <div className="AnalyticsColumn wide">
                        <h3 className="AnalyticsHeader">Most Liked Content</h3>
                        <Bar options={barChartOptions} data={likedChartData} />
                    </div>
                    <div className="AnalyticsColumn wide">
                        <h3 className="AnalyticsHeader">Most Disliked Content</h3>
                        <Bar options={barChartOptions} data={dislikedChartData} />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default AnalyticsDashboard;
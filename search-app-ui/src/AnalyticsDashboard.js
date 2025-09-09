import React, { useState, useEffect } from 'react';
import './App.css'; // We'll reuse the same CSS file

function AnalyticsDashboard({ apiBaseUrl }) {
    const [analyticsData, setAnalyticsData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const response = await fetch(`${apiBaseUrl}/analytics`);
                const data = await response.json();
                setAnalyticsData(data);
            } catch (error) {
                console.error("Error fetching analytics:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchAnalytics();
    }, [apiBaseUrl]);

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
                <h3 className="AnalyticsHeader">📊 Top Searches</h3>
                <ul className="AnalyticsList">
                    {analyticsData?.top_searches.map((item, index) => (
                        <li key={index} className="AnalyticsListItem">
                            <span>{item.query}</span>
                            <span className="AnalyticsCount">{item.count}</span>
                        </li>
                    ))}
                </ul>
            </div>
            <div className="AnalyticsColumn">
                <h3 className="AnalyticsHeader">❓ Content Gaps (Searches with No Results)</h3>
                <ul className="AnalyticsList">
                    {analyticsData?.content_gaps.map((item, index) => (
                        <li key={index} className="AnalyticsListItem">
                            <span>{item.query}</span>
                            <span className="AnalyticsCount">{item.count}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}

export default AnalyticsDashboard;
window.renderCharts = function(chartsData) {
    if (!chartsData) return;

    // Chart.js global configuration defaults for premium design aesthetics
    if (window.Chart) {
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.color = '#4b5563'; // Tailwind text-gray-600
        Chart.defaults.responsive = true;
        Chart.defaults.maintainAspectRatio = false;

        // --- KPI 1: Revenue Trend Line Chart ---
        if (chartsData.revenue_trend && document.getElementById('revenueTrendChart')) {
            const ctx = document.getElementById('revenueTrendChart').getContext('2d');
            
            // Premium gradient fill
            const gradient = ctx.createLinearGradient(0, 0, 0, 250);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.35)');  // Indigo
            gradient.addColorStop(1, 'rgba(99, 102, 241, 0.00)');

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartsData.revenue_trend.labels,
                    datasets: [{
                        label: 'Earnings (INR)',
                        data: chartsData.revenue_trend.data,
                        fill: true,
                        backgroundColor: gradient,
                        borderColor: 'rgb(99, 102, 241)',
                        borderWidth: 2.5,
                        tension: 0.3,
                        pointBackgroundColor: 'rgb(99, 102, 241)',
                        pointHoverRadius: 6,
                        pointRadius: 3
                    }]
                },
                options: {
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f3f4f6' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // --- KPI 2: Lawyer Onboarding Bar Chart ---
        if (chartsData.lawyer_onboarding && document.getElementById('lawyerOnboardingChart')) {
            const ctx = document.getElementById('lawyerOnboardingChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: chartsData.lawyer_onboarding.labels,
                    datasets: [{
                        data: chartsData.lawyer_onboarding.data,
                        backgroundColor: [
                            'rgba(16, 185, 129, 0.8)', // Emerald Verified
                            'rgba(245, 158, 11, 0.8)'  // Amber Pending
                        ],
                        borderColor: [
                            'rgb(16, 185, 129)',
                            'rgb(245, 158, 11)'
                        ],
                        borderWidth: 1.5,
                        borderRadius: 6,
                        barThickness: 35
                    }]
                },
                options: {
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f3f4f6' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // --- KPI 3: User Growth Line Chart ---
        if (chartsData.user_growth && document.getElementById('userGrowthChart')) {
            const ctx = document.getElementById('userGrowthChart').getContext('2d');
            
            // Premium gradient fill
            const gradient = ctx.createLinearGradient(0, 0, 0, 250);
            gradient.addColorStop(0, 'rgba(20, 184, 166, 0.35)');  // Teal
            gradient.addColorStop(1, 'rgba(20, 184, 166, 0.00)');

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartsData.user_growth.labels,
                    datasets: [{
                        label: 'Total Registered Clients',
                        data: chartsData.user_growth.data,
                        fill: true,
                        backgroundColor: gradient,
                        borderColor: 'rgb(20, 184, 166)',
                        borderWidth: 2.5,
                        tension: 0.3,
                        pointBackgroundColor: 'rgb(20, 184, 166)',
                        pointHoverRadius: 6,
                        pointRadius: 3
                    }]
                },
                options: {
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f3f4f6' }
                        },
                        x: {
                            grid: { display: false }
                        }
                    }
                }
            });
        }

        // --- KPI 4: Case Status Breakdown Doughnut Chart ---
        if (chartsData.case_breakdown && document.getElementById('caseBreakdownChart')) {
            const ctx = document.getElementById('caseBreakdownChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chartsData.case_breakdown.labels,
                    datasets: [{
                        data: chartsData.case_breakdown.data,
                        backgroundColor: [
                            'rgba(245, 158, 11, 0.75)',  // Amber for PENDING
                            'rgba(59, 130, 246, 0.75)',  // Blue for ACTIVE
                            'rgba(239, 68, 68, 0.75)',   // Red for REJECTED
                            'rgba(16, 185, 129, 0.75)',  // Emerald for COMPLETED
                            'rgba(139, 92, 246, 0.75)',  // Purple
                            'rgba(107, 114, 128, 0.75)'   // Gray
                        ],
                        borderWidth: 1.5,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 12,
                                padding: 12,
                                font: { size: 11 }
                            }
                        }
                    },
                    cutout: '65%'
                }
            });
        }
    }
};

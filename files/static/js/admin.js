document.addEventListener('DOMContentLoaded', function() {
    const chartData = JSON.parse(document.getElementById('chart-data').textContent);

    const bloodGroupCtx = document.getElementById('bloodGroupChart').getContext('2d');
    new Chart(bloodGroupCtx, {
        type: 'pie',
        data: {
            labels: chartData.blood_groups,
            datasets: [{
                data: chartData.blood_group_counts,
                backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF']
            }]
        }
    });

    const donationCtx = document.getElementById('donationChart').getContext('2d');
    new Chart(donationCtx, {
        type: 'line',
        data: {
            labels: chartData.months,
            datasets: [{
                label: 'Donations',
                data: chartData.monthly_donations,
                borderColor: '#C0392B',
                backgroundColor: 'rgba(192, 57, 43, 0.1)'
            }]
        }
    });
});
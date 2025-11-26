/**
 * Israeli Basketball Calendar - Frontend Application
 */

// DOM Elements
const seasonSelect = document.getElementById('season-select');
const competitionsContainer = document.getElementById('competitions-container');
const teamFilter = document.getElementById('team-filter');
const teamSuggestions = document.getElementById('team-suggestions');
const daysRange = document.getElementById('days-range');
const daysValue = document.getElementById('days-value');
const calendarUrl = document.getElementById('calendar-url');
const copyBtn = document.getElementById('copy-btn');
const copyFeedback = document.getElementById('copy-feedback');
const generateBtn = document.getElementById('generate-btn');
const googleCalendarLink = document.getElementById('google-calendar-link');

// State
let seasons = [];
let competitions = [];
let teams = [];
let selectedSeason = null;
let selectedCompetitions = new Set();
let selectedTeam = '';

// Days mapping
const daysMap = {
    0: 7,
    1: 14,
    2: 30,
    3: 90,
    4: null // All
};

const daysLabels = {
    0: '7 ימים',
    1: '14 ימים',
    2: '30 ימים',
    3: '90 ימים',
    4: 'כל המשחקים'
};

// API Functions
async function fetchSeasons() {
    try {
        const response = await fetch('/api/seasons');
        if (!response.ok) throw new Error('Failed to fetch seasons');
        seasons = await response.json();
        populateSeasons();
    } catch (error) {
        console.error('Error fetching seasons:', error);
        seasonSelect.innerHTML = '<option value="">שגיאה בטעינת עונות</option>';
    }
}

async function fetchCompetitions(seasonId) {
    try {
        competitionsContainer.innerHTML = '<p class="placeholder">טוען ליגות...</p>';
        const response = await fetch(`/api/competitions/${seasonId}`);
        if (!response.ok) throw new Error('Failed to fetch competitions');
        competitions = await response.json();
        populateCompetitions();
    } catch (error) {
        console.error('Error fetching competitions:', error);
        competitionsContainer.innerHTML = '<p class="placeholder">שגיאה בטעינת ליגות</p>';
    }
}

async function fetchTeams(seasonId) {
    try {
        const response = await fetch(`/api/teams/${seasonId}`);
        if (!response.ok) throw new Error('Failed to fetch teams');
        teams = await response.json();
    } catch (error) {
        console.error('Error fetching teams:', error);
        teams = [];
    }
}

// UI Functions
function populateSeasons() {
    seasonSelect.innerHTML = '<option value="">בחר עונה</option>';

    // Sort seasons by name descending (newest first)
    seasons.sort((a, b) => b.name.localeCompare(a.name));

    seasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season.id;
        option.textContent = season.name;
        option.dataset.name = season.name;
        if (season.isCurrent) {
            option.textContent += ' (נוכחית)';
            option.selected = true;
            selectedSeason = season;
        }
        seasonSelect.appendChild(option);
    });

    // Auto-select current season
    if (selectedSeason) {
        fetchCompetitions(selectedSeason.id);
        fetchTeams(selectedSeason.id);
    }
}

function populateCompetitions() {
    competitionsContainer.innerHTML = '';
    selectedCompetitions.clear();

    if (competitions.length === 0) {
        competitionsContainer.innerHTML = '<p class="placeholder">לא נמצאו ליגות לעונה זו</p>';
        return;
    }

    competitions.forEach(comp => {
        const label = document.createElement('label');
        label.className = 'checkbox-label';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = comp.name;
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                selectedCompetitions.add(comp.name);
            } else {
                selectedCompetitions.delete(comp.name);
            }
            updateUrl();
        });

        const span = document.createElement('span');
        span.textContent = comp.name;

        label.appendChild(checkbox);
        label.appendChild(span);
        competitionsContainer.appendChild(label);
    });
}

function updateTeamSuggestions() {
    const query = teamFilter.value.trim().toLowerCase();
    teamSuggestions.innerHTML = '';

    if (query.length < 2) {
        return;
    }

    const matches = teams.filter(team =>
        team.name.toLowerCase().includes(query)
    ).slice(0, 6);

    matches.forEach(team => {
        const chip = document.createElement('span');
        chip.className = 'suggestion-chip';
        if (selectedTeam === team.name) {
            chip.classList.add('selected');
        }
        chip.textContent = team.name;
        chip.addEventListener('click', () => {
            if (selectedTeam === team.name) {
                selectedTeam = '';
                teamFilter.value = '';
            } else {
                selectedTeam = team.name;
                teamFilter.value = team.name;
            }
            updateTeamSuggestions();
            updateUrl();
        });
        teamSuggestions.appendChild(chip);
    });
}

function updateDaysDisplay() {
    const value = parseInt(daysRange.value);
    daysValue.textContent = daysLabels[value];
}

function getBaseUrl() {
    return window.location.origin;
}

function buildCalendarUrl() {
    const params = new URLSearchParams();

    // Get selected season name
    const selectedOption = seasonSelect.options[seasonSelect.selectedIndex];
    if (selectedOption && selectedOption.dataset.name) {
        params.set('season', selectedOption.dataset.name);
    }

    // Add competition filter (only if one is selected)
    if (selectedCompetitions.size === 1) {
        params.set('competition', [...selectedCompetitions][0]);
    }

    // Add team filter
    if (selectedTeam) {
        params.set('team', selectedTeam);
    }

    // Add days filter
    const daysIndex = parseInt(daysRange.value);
    const days = daysMap[daysIndex];
    if (days !== null) {
        params.set('days', days.toString());
    }

    // Add status filter
    const statusRadio = document.querySelector('input[name="status"]:checked');
    if (statusRadio && statusRadio.value !== 'all') {
        params.set('status', statusRadio.value);
    }

    return `${getBaseUrl()}/calendar.ics?${params.toString()}`;
}

function updateUrl() {
    const url = buildCalendarUrl();
    calendarUrl.value = url;
    updateGoogleCalendarLink(url);
}

function updateGoogleCalendarLink(url) {
    // Convert http/https to webcal for subscription
    const webcalUrl = url.replace(/^https?:/, 'webcal:');
    // Google Calendar add by URL
    const googleUrl = `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcalUrl)}`;
    googleCalendarLink.href = googleUrl;
}

async function copyToClipboard() {
    const url = calendarUrl.value;
    if (!url) {
        showFeedback('אנא צור כתובת יומן קודם', 'error');
        return;
    }

    try {
        await navigator.clipboard.writeText(url);
        showFeedback('הכתובת הועתקה בהצלחה!', 'success');
    } catch (err) {
        // Fallback for older browsers
        calendarUrl.select();
        document.execCommand('copy');
        showFeedback('הכתובת הועתקה בהצלחה!', 'success');
    }
}

function showFeedback(message, type) {
    copyFeedback.textContent = message;
    copyFeedback.className = `feedback ${type}`;
    setTimeout(() => {
        copyFeedback.textContent = '';
        copyFeedback.className = 'feedback';
    }, 3000);
}

// Event Listeners
seasonSelect.addEventListener('change', async (e) => {
    const seasonId = e.target.value;
    if (!seasonId) {
        competitionsContainer.innerHTML = '<p class="placeholder">בחר עונה כדי לראות ליגות</p>';
        selectedSeason = null;
        return;
    }

    selectedSeason = seasons.find(s => s.id === seasonId);
    await Promise.all([
        fetchCompetitions(seasonId),
        fetchTeams(seasonId)
    ]);
    updateUrl();
});

teamFilter.addEventListener('input', () => {
    selectedTeam = teamFilter.value.trim();
    updateTeamSuggestions();
    updateUrl();
});

daysRange.addEventListener('input', () => {
    updateDaysDisplay();
    updateUrl();
});

document.querySelectorAll('input[name="status"]').forEach(radio => {
    radio.addEventListener('change', updateUrl);
});

generateBtn.addEventListener('click', updateUrl);
copyBtn.addEventListener('click', copyToClipboard);

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateDaysDisplay();
    fetchSeasons();
});

// Israeli Basketball Calendar - Frontend Application
// Cascading Filter: Season -> League -> Team

const API_BASE = '';

// State
let state = {
    seasons: [],
    competitions: {},  // keyed by season_id
    teams: {},         // keyed by group_id
    matches: [],
    filters: {
        season: '',
        seasonName: '',
        league: '',      // group_id
        leagueName: '',  // competition name for URL
        team: '',
        teamName: ''
    }
};

// DOM Elements
const elements = {
    // Filter steps
    seasonSelect: document.getElementById('season-select'),
    leagueSelect: document.getElementById('league-select'),
    teamSelect: document.getElementById('team-select'),
    leagueStep: document.getElementById('league-step'),
    teamStep: document.getElementById('team-step'),

    // Preview
    matchesPreview: document.getElementById('matches-preview'),
    matchesCount: document.getElementById('matches-count'),

    // Calendar
    calendarUrl: document.getElementById('calendar-url'),
    copyBtn: document.getElementById('copy-btn'),
    googleLink: document.getElementById('google-calendar-link'),
    downloadLink: document.getElementById('download-link'),

    // Footer
    cacheStatus: document.getElementById('cache-status'),
    lastUpdate: document.getElementById('last-update'),
    refreshBtn: document.getElementById('refresh-btn'),
    toast: document.getElementById('toast')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadInitialData();
    setupEventListeners();
    updateStepStates();
});

// Load initial data
async function loadInitialData() {
    try {
        const [seasons, cacheInfo] = await Promise.all([
            fetchAPI('/api/seasons'),
            fetchAPI('/api/cache-info')
        ]);

        state.seasons = seasons || [];
        populateSeasons();
        updateCacheStatus(cacheInfo);
        updateCalendarUrl();

        // Show empty state
        elements.matchesPreview.innerHTML = '<p class="loading">בחר עונה וליגה להצגת משחקים</p>';
        elements.matchesCount.textContent = '';

    } catch (error) {
        console.error('Error loading initial data:', error);
        showToast('שגיאה בטעינת נתונים', 'error');
    }
}

// API helper
async function fetchAPI(endpoint) {
    const response = await fetch(API_BASE + endpoint);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}

// Populate seasons dropdown
function populateSeasons() {
    elements.seasonSelect.innerHTML = '<option value="">בחר עונה...</option>';

    // Sort seasons by name descending (newest first)
    const sortedSeasons = [...state.seasons].sort((a, b) =>
        (b.name || '').localeCompare(a.name || '', 'he')
    );

    sortedSeasons.forEach(season => {
        const option = document.createElement('option');
        option.value = season._id || season.id;
        option.textContent = season.name;
        elements.seasonSelect.appendChild(option);
    });
}

// Populate leagues dropdown based on selected season
async function populateLeagues(seasonId) {
    elements.leagueSelect.innerHTML = '<option value="">טוען ליגות...</option>';
    elements.leagueSelect.disabled = true;

    try {
        // Check if we have cached competitions for this season
        if (!state.competitions[seasonId]) {
            const competitions = await fetchAPI(`/api/competitions/${seasonId}`);
            state.competitions[seasonId] = competitions || [];
        }

        const competitions = state.competitions[seasonId];
        elements.leagueSelect.innerHTML = '<option value="">בחר ליגה...</option>';

        // Flatten competitions and their groups, then sort
        const leagueOptions = [];
        competitions.forEach(comp => {
            const groups = comp.groups || [];
            groups.forEach(group => {
                const displayName = group.name !== comp.name && group.name !== 'רגילה'
                    ? `${comp.name} - ${group.name}`
                    : comp.name;
                leagueOptions.push({
                    id: group.id,
                    competitionName: comp.name,
                    groupName: group.name,
                    displayName: displayName
                });
            });
        });

        // Sort leagues alphabetically by display name
        leagueOptions.sort((a, b) => a.displayName.localeCompare(b.displayName, 'he'));

        leagueOptions.forEach(league => {
            const option = document.createElement('option');
            option.value = league.id;
            option.dataset.competitionName = league.competitionName;
            option.dataset.groupName = league.groupName;
            option.textContent = league.displayName;
            elements.leagueSelect.appendChild(option);
        });

        elements.leagueSelect.disabled = false;

    } catch (error) {
        console.error('Error loading leagues:', error);
        elements.leagueSelect.innerHTML = '<option value="">שגיאה בטעינת ליגות</option>';
        showToast('שגיאה בטעינת ליגות', 'error');
    }
}

// Populate teams dropdown based on selected league
async function populateTeams(groupId, competitionName) {
    elements.teamSelect.innerHTML = '<option value="">טוען קבוצות...</option>';
    elements.teamSelect.disabled = true;

    try {
        // Get matches for this group to extract teams
        if (!state.teams[groupId]) {
            const matches = await fetchAPI(`/api/matches?competition=${encodeURIComponent(competitionName)}&season=${state.filters.season}`);

            // Extract unique teams from matches
            const teamsMap = {};
            matches.forEach(match => {
                if (match.homeTeam?.id) {
                    teamsMap[match.homeTeam.id] = match.homeTeam.name;
                }
                if (match.awayTeam?.id) {
                    teamsMap[match.awayTeam.id] = match.awayTeam.name;
                }
            });

            // Convert to sorted array
            state.teams[groupId] = Object.entries(teamsMap)
                .map(([id, name]) => ({ id, name }))
                .sort((a, b) => a.name.localeCompare(b.name, 'he'));
        }

        const teams = state.teams[groupId];

        if (teams.length === 0) {
            // No teams found - data not available for this league
            elements.teamSelect.innerHTML = '<option value="">אין נתונים זמינים לליגה זו</option>';
            elements.teamSelect.disabled = true;
            showToast('אין נתוני משחקים זמינים לליגה זו. נסה לרענן את הנתונים.', 'error');
            return;
        }

        elements.teamSelect.innerHTML = '<option value="">כל הקבוצות</option>';

        teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team.id;
            option.dataset.teamName = team.name;
            option.textContent = team.name;
            elements.teamSelect.appendChild(option);
        });

        elements.teamSelect.disabled = false;

    } catch (error) {
        console.error('Error loading teams:', error);
        elements.teamSelect.innerHTML = '<option value="">כל הקבוצות (שגיאה בטעינה)</option>';
        elements.teamSelect.disabled = false;  // Still allow "all teams" selection
    }
}

// Setup event listeners
function setupEventListeners() {
    // Cascading filter changes
    elements.seasonSelect.addEventListener('change', onSeasonChange);
    elements.leagueSelect.addEventListener('change', onLeagueChange);
    elements.teamSelect.addEventListener('change', onTeamChange);

    // Copy button
    elements.copyBtn.addEventListener('click', copyCalendarUrl);

    // Refresh button
    elements.refreshBtn.addEventListener('click', refreshData);
}

// Season change handler
async function onSeasonChange() {
    const seasonId = elements.seasonSelect.value;
    const seasonOption = elements.seasonSelect.selectedOptions[0];

    state.filters.season = seasonId;
    state.filters.seasonName = seasonOption?.textContent || '';

    // Reset downstream filters
    state.filters.league = '';
    state.filters.leagueName = '';
    state.filters.team = '';
    state.filters.teamName = '';

    // Reset league and team dropdowns
    elements.leagueSelect.innerHTML = '<option value="">בחר עונה תחילה...</option>';
    elements.leagueSelect.disabled = true;
    elements.teamSelect.innerHTML = '<option value="">בחר ליגה תחילה...</option>';
    elements.teamSelect.disabled = true;

    if (seasonId) {
        await populateLeagues(seasonId);
    }

    updateStepStates();
    updateCalendarUrl();
    loadMatches();
}

// League change handler
async function onLeagueChange() {
    const groupId = elements.leagueSelect.value;
    const leagueOption = elements.leagueSelect.selectedOptions[0];

    state.filters.league = groupId;
    state.filters.leagueName = leagueOption?.dataset.competitionName || '';

    // Reset team filter
    state.filters.team = '';
    state.filters.teamName = '';
    elements.teamSelect.innerHTML = '<option value="">בחר ליגה תחילה...</option>';
    elements.teamSelect.disabled = true;

    if (groupId && state.filters.leagueName) {
        await populateTeams(groupId, state.filters.leagueName);
    }

    updateStepStates();
    updateCalendarUrl();
    loadMatches();
}

// Team change handler
function onTeamChange() {
    const teamId = elements.teamSelect.value;
    const teamOption = elements.teamSelect.selectedOptions[0];

    state.filters.team = teamId;
    state.filters.teamName = teamOption?.dataset.teamName || '';

    updateStepStates();
    updateCalendarUrl();
    loadMatches();
}

// Update visual state of filter steps
function updateStepStates() {
    const steps = document.querySelectorAll('.filter-step');

    // Step 1: Season
    const step1 = steps[0];
    step1.classList.remove('active', 'completed', 'disabled');
    if (state.filters.season) {
        step1.classList.add('completed');
    } else {
        step1.classList.add('active');
    }

    // Step 2: League
    const step2 = steps[1];
    step2.classList.remove('active', 'completed', 'disabled');
    if (!state.filters.season) {
        step2.classList.add('disabled');
    } else if (state.filters.league) {
        step2.classList.add('completed');
    } else {
        step2.classList.add('active');
    }

    // Step 3: Team
    const step3 = steps[2];
    step3.classList.remove('active', 'completed', 'disabled');
    if (!state.filters.league) {
        step3.classList.add('disabled');
    } else if (state.filters.team) {
        step3.classList.add('completed');
    } else {
        step3.classList.add('active');
    }
}

// Load matches based on current filters
async function loadMatches() {
    // Require at least season and league selection
    if (!state.filters.season || !state.filters.league) {
        elements.matchesPreview.innerHTML = '<p class="loading">בחר עונה וליגה להצגת משחקים</p>';
        elements.matchesCount.textContent = '';
        return;
    }

    elements.matchesPreview.innerHTML = '<p class="loading">טוען משחקים...</p>';

    try {
        const params = new URLSearchParams();
        params.set('season', state.filters.season);
        if (state.filters.leagueName) {
            params.set('competition', state.filters.leagueName);
        }
        if (state.filters.teamName) {
            params.set('team', state.filters.teamName);
        }

        const matches = await fetchAPI(`/api/matches?${params.toString()}`);
        state.matches = matches || [];

        // Display all matches (no date filtering)
        displayMatches(state.matches);
    } catch (error) {
        console.error('Error loading matches:', error);
        elements.matchesPreview.innerHTML = '<p class="loading">שגיאה בטעינת משחקים</p>';
    }
}

// Display matches in preview
function displayMatches(matches) {
    if (matches.length === 0) {
        elements.matchesPreview.innerHTML = '<p class="loading">אין נתוני משחקים זמינים לליגה זו. לחץ על "רענן נתונים" לטעינת נתונים חדשים.</p>';
        elements.matchesCount.textContent = '';
        return;
    }

    elements.matchesPreview.innerHTML = matches.slice(0, 100).map(match => {
        const home = match.homeTeam?.name || 'TBD';
        const away = match.awayTeam?.name || 'TBD';
        const date = formatDate(match.date);
        const status = getStatusDisplay(match);
        const location = match.court?.place || '';

        let teams = `${home} נגד ${away}`;
        if (match.status === 'CLOSED' && match.score?.totals) {
            const homeScore = getScore(match, 'home');
            const awayScore = getScore(match, 'away');
            teams = `${home} ${homeScore}-${awayScore} ${away}`;
        }

        return `
            <div class="match-item">
                <div>
                    <div class="match-teams">${teams}</div>
                    <div class="match-meta">${date}${location ? ' | ' + location : ''}</div>
                </div>
                <span class="match-status ${status.class}">${status.text}</span>
            </div>
        `;
    }).join('');

    elements.matchesCount.textContent = `מציג ${Math.min(matches.length, 100)} מתוך ${matches.length} משחקים`;
}

// Get score for a team
function getScore(match, side) {
    const teamId = side === 'home' ? match.homeTeam?.id : match.awayTeam?.id;
    const totals = match.score?.totals || [];
    const total = totals.find(t => t.teamId === teamId);
    return total?.total || 0;
}

// Get status display
function getStatusDisplay(match) {
    switch (match.status) {
        case 'CLOSED':
            return { text: 'הסתיים', class: 'closed' };
        case 'LIVE':
            return { text: 'עכשיו', class: 'live' };
        default:
            return { text: 'צפוי', class: 'upcoming' };
    }
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('he-IL', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Update calendar URL
function updateCalendarUrl() {
    const params = new URLSearchParams();

    if (state.filters.season) params.set('season', state.filters.season);
    if (state.filters.leagueName) params.set('competition', state.filters.leagueName);
    if (state.filters.teamName) params.set('team', state.filters.teamName);

    const baseUrl = window.location.origin;
    const calendarPath = '/calendar.ics';
    const queryString = params.toString();

    const fullUrl = queryString ? `${baseUrl}${calendarPath}?${queryString}` : `${baseUrl}${calendarPath}`;

    elements.calendarUrl.value = fullUrl;
    elements.downloadLink.href = `${calendarPath}?${queryString}`;

    // Google Calendar subscribe URL
    const googleUrl = `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(fullUrl)}`;
    elements.googleLink.href = googleUrl;
}

// Copy calendar URL to clipboard
async function copyCalendarUrl() {
    try {
        await navigator.clipboard.writeText(elements.calendarUrl.value);
        showToast('הכתובת הועתקה!', 'success');
    } catch (error) {
        // Fallback for older browsers
        elements.calendarUrl.select();
        document.execCommand('copy');
        showToast('הכתובת הועתקה!', 'success');
    }
}

// Refresh data with async polling
async function refreshData() {
    elements.refreshBtn.disabled = true;
    elements.refreshBtn.textContent = 'מרענן...';

    try {
        // Start the background refresh
        const response = await fetch(API_BASE + '/api/refresh', { method: 'POST' });
        const result = await response.json();

        if (result.status === 'in_progress') {
            showToast('רענון כבר מתבצע, אנא המתן...', 'info');
        } else if (result.status === 'started') {
            showToast('רענון נתונים התחיל. הפעולה עשויה להימשך 30-60 שניות...', 'info');
        }

        // Poll for completion
        await pollRefreshStatus();

        showToast('הנתונים עודכנו!', 'success');

        // Clear cached data and reload
        state.competitions = {};
        state.teams = {};

        await loadInitialData();
    } catch (error) {
        console.error('Error refreshing data:', error);
        showToast('שגיאה ברענון נתונים', 'error');
    } finally {
        elements.refreshBtn.disabled = false;
        elements.refreshBtn.textContent = 'רענן נתונים';
    }
}

// Poll refresh status until complete
async function pollRefreshStatus() {
    const maxAttempts = 18; // Max 3 minutes (18 * 10 seconds)
    let attempts = 0;

    while (attempts < maxAttempts) {
        await sleep(10000); // Wait 10 seconds between polls

        try {
            const response = await fetch(API_BASE + '/api/refresh-status');
            const status = await response.json();

            if (!status.is_scraping) {
                // Scraping is done - check if there was an error
                if (status.last_error) {
                    throw new Error(status.last_error);
                }
                return;
            }

            // Update button text with progress indicator
            const dots = '.'.repeat((attempts % 3) + 1);
            elements.refreshBtn.textContent = `מרענן${dots}`;

            attempts++;
        } catch (error) {
            console.error('Error checking refresh status:', error);
            throw error; // Re-throw to show error to user
        }
    }

    // Timeout after max attempts
    throw new Error('Refresh timeout');
}

// Sleep helper
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Update cache status display
function updateCacheStatus(cacheInfo) {
    if (!cacheInfo || !cacheInfo.exists) {
        elements.cacheStatus.textContent = 'אין נתונים במטמון';
        elements.cacheStatus.style.backgroundColor = '#ffebee';
        elements.lastUpdate.textContent = '-';
        return;
    }

    if (cacheInfo.stale) {
        elements.cacheStatus.textContent = 'נתונים ישנים';
        elements.cacheStatus.style.backgroundColor = '#fff3e0';
    } else {
        elements.cacheStatus.textContent = 'נתונים עדכניים';
        elements.cacheStatus.style.backgroundColor = '#e8f5e9';
    }

    if (cacheInfo.last_updated) {
        const date = new Date(cacheInfo.last_updated);
        elements.lastUpdate.textContent = date.toLocaleString('he-IL');
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type} show`;

    setTimeout(() => {
        elements.toast.className = 'toast';
    }, 3000);
}

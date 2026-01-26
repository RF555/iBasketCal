// Israeli Basketball Calendar - Frontend Application
// Cascading Filter: Season -> League -> Team

const API_BASE = '';

// API returns Hebrew group names - this constant represents "Regular" group
// which is used to filter display names (show just competition name, not "Competition - Regular")
const API_GROUP_NAME_REGULAR = 'רגילה';

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
    },
    // Calendar mode settings
    mode: 'fan',       // 'fan' or 'player'
    prepHours: 1,      // 0-3
    prepMinutes: 0,    // 0, 15, 30, 45
    prepTime: 60,      // total minutes (calculated)
    timeFormat: '24h', // '24h' or '12h'
    timezone: 'Asia/Jerusalem',  // IANA timezone
    // Backend-generated calendar URLs
    calendarUrls: null  // { ics_url, webcal_url, google_url, outlook365_url, outlook_url }
};

// Store last cache info for re-render on language change
let lastCacheInfo = null;

// DOM Elements
const elements = {
    // Filter steps
    seasonSelect: document.getElementById('season-select'),
    leagueSelect: document.getElementById('league-select'),
    teamSelect: document.getElementById('team-select'),
    leagueStep: document.getElementById('league-step'),
    teamStep: document.getElementById('team-step'),
    modeStep: document.getElementById('mode-step'),

    // Mode selection
    playerModeCheckbox: document.getElementById('player-mode-checkbox'),
    prepTimeContainer: document.getElementById('prep-time-container'),
    prepHoursSelect: document.getElementById('prep-hours-select'),
    prepMinutesSelect: document.getElementById('prep-minutes-select'),
    timeFormat24h: document.getElementById('time-format-24h'),
    timeFormat12h: document.getElementById('time-format-12h'),
    timezoneSelect: document.getElementById('timezone-select'),

    // Preview
    matchesPreview: document.getElementById('matches-preview'),
    matchesCount: document.getElementById('matches-count'),

    // Calendar
    calendarUrl: document.getElementById('calendar-url'),
    copyBtn: document.getElementById('copy-btn'),
    googleLink: document.getElementById('google-calendar-link'),
    appleLink: document.getElementById('apple-calendar-link'),
    outlookDropdown: document.querySelector('.dropdown'),
    outlookDropdownBtn: document.getElementById('outlook-dropdown-btn'),
    outlookDropdownMenu: document.getElementById('outlook-dropdown-menu'),
    outlook365Link: document.getElementById('outlook-365-link'),
    outlookComLink: document.getElementById('outlook-com-link'),
    downloadLink: document.getElementById('download-link'),

    // Footer
    lastUpdate: document.getElementById('last-update'),
    refreshBtn: document.getElementById('refresh-btn'),
    toast: document.getElementById('toast')
};

// Initialize with i18n
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize i18next first
    await initI18next();
    updateDocumentDirection(getCurrentLanguage());
    translatePage();

    // Now initialize the app
    loadInitialData();
    setupEventListeners();
    updateStepStates();
});

// Listen for language changes to update dynamic content
window.addEventListener('languageChanged', async () => {
    // Re-render dynamic content with new language
    populateSeasons();

    // Update dropdowns placeholder text based on state
    if (!state.filters.season) {
        elements.leagueSelect.innerHTML = `<option value="">${t('filters.league.selectFirst')}</option>`;
        elements.teamSelect.innerHTML = `<option value="">${t('filters.team.selectFirst')}</option>`;
    } else if (!state.filters.league) {
        elements.teamSelect.innerHTML = `<option value="">${t('filters.team.selectFirst')}</option>`;
    }

    // Re-render matches if we have any
    if (state.matches.length > 0) {
        displayMatches(state.matches);
    } else if (state.filters.season && state.filters.league) {
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.loading')}</p>`;
    } else {
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.selectFilters')}</p>`;
    }

    // Update cache status
    if (lastCacheInfo) {
        updateCacheStatus(lastCacheInfo);
    }

    // Update calendar URL to refresh calendar name translation
    await updateCalendarUrl();
});


// Load initial data
async function loadInitialData() {
    try {
        const [seasons, cacheInfo] = await Promise.all([
            fetchAPI('/api/seasons'),
            fetchAPI('/api/cache-info')
        ]);

        state.seasons = seasons || [];
        lastCacheInfo = cacheInfo;
        populateSeasons();
        updateCacheStatus(cacheInfo);
        await updateCalendarUrl();

        // Show empty state
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.selectFilters')}</p>`;
        elements.matchesCount.textContent = '';

    } catch (error) {
        console.error('Error loading initial data:', error);
        showToast(t('toast.loadError'), 'error');
    }
}

// API helper with timeout support
async function fetchAPI(endpoint, options = {}) {
    const timeout = options.timeout || 30000; // Default 30 second timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(API_BASE + endpoint, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        return response.json();
    } catch (error) {
        clearTimeout(timeoutId);

        if (error.name === 'AbortError') {
            throw new Error(t('toast.timeout'));
        }
        throw error;
    }
}

// Populate seasons dropdown
function populateSeasons() {
    elements.seasonSelect.innerHTML = `<option value="">${t('filters.season.placeholder')}</option>`;

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

    // Restore selection if we had one
    if (state.filters.season) {
        elements.seasonSelect.value = state.filters.season;
    }
}

// Populate leagues dropdown based on selected season
async function populateLeagues(seasonId) {
    elements.leagueSelect.innerHTML = `<option value="">${t('filters.league.loading')}</option>`;
    elements.leagueSelect.disabled = true;

    try {
        // Check if we have cached competitions for this season
        if (!state.competitions[seasonId]) {
            const competitions = await fetchAPI(`/api/competitions/${seasonId}`);
            state.competitions[seasonId] = competitions || [];
        }

        const competitions = state.competitions[seasonId];
        elements.leagueSelect.innerHTML = `<option value="">${t('filters.league.placeholder')}</option>`;

        // Flatten competitions and their groups, then sort
        const leagueOptions = [];
        competitions.forEach(comp => {
            const groups = comp.groups || [];
            groups.forEach(group => {
                const displayName = group.name !== comp.name && group.name !== API_GROUP_NAME_REGULAR
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
        elements.leagueSelect.innerHTML = `<option value="">${t('toast.leagueError')}</option>`;
        showToast(t('toast.leagueError'), 'error');
    }
}

// Populate teams dropdown based on selected league
// Uses the efficient /api/teams?group_id endpoint instead of fetching all matches
async function populateTeams(groupId) {
    elements.teamSelect.innerHTML = `<option value="">${t('filters.team.loading')}</option>`;
    elements.teamSelect.disabled = true;

    try {
        // Use the new efficient endpoint - only fetches teams for this group
        if (!state.teams[groupId]) {
            const teams = await fetchAPI(`/api/teams?group_id=${encodeURIComponent(groupId)}`);
            // Teams are already sorted by name from the API
            state.teams[groupId] = teams || [];
        }

        const teams = state.teams[groupId];

        if (teams.length === 0) {
            // No teams found - data not available for this league
            elements.teamSelect.innerHTML = `<option value="">${t('filters.team.noData')}</option>`;
            elements.teamSelect.disabled = true;
            showToast(t('toast.noMatchData'), 'error');
            return;
        }

        elements.teamSelect.innerHTML = `<option value="">${t('filters.team.allTeams')}</option>`;

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
        elements.teamSelect.innerHTML = `<option value="">${t('filters.team.allTeamsError')}</option>`;
        elements.teamSelect.disabled = false;  // Still allow "all teams" selection
    }
}

// Setup event listeners
function setupEventListeners() {
    // Cascading filter changes
    elements.seasonSelect.addEventListener('change', onSeasonChange);
    elements.leagueSelect.addEventListener('change', onLeagueChange);
    elements.teamSelect.addEventListener('change', onTeamChange);

    // Mode selection changes
    elements.playerModeCheckbox.addEventListener('change', onModeChange);
    elements.prepHoursSelect.addEventListener('change', onPrepTimeChange);
    elements.prepMinutesSelect.addEventListener('change', onPrepTimeChange);
    elements.timeFormat24h.addEventListener('change', onTimeFormatChange);
    elements.timeFormat12h.addEventListener('change', onTimeFormatChange);
    elements.timezoneSelect.addEventListener('change', onTimezoneChange);

    // Copy button
    elements.copyBtn.addEventListener('click', copyCalendarUrl);

    // Refresh button
    elements.refreshBtn.addEventListener('click', refreshData);

    // Outlook dropdown toggle
    elements.outlookDropdownBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        elements.outlookDropdownMenu.classList.toggle('show');
        elements.outlookDropdown.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', () => {
        elements.outlookDropdownMenu.classList.remove('show');
        elements.outlookDropdown.classList.remove('open');
    });

    // Prevent dropdown from closing when clicking inside the menu
    elements.outlookDropdownMenu.addEventListener('click', (e) => {
        // Allow the links to navigate, but close dropdown after
        setTimeout(() => {
            elements.outlookDropdownMenu.classList.remove('show');
            elements.outlookDropdown.classList.remove('open');
        }, 100);
    });
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
    elements.leagueSelect.innerHTML = `<option value="">${t('filters.league.selectFirst')}</option>`;
    elements.leagueSelect.disabled = true;
    elements.teamSelect.innerHTML = `<option value="">${t('filters.team.selectFirst')}</option>`;
    elements.teamSelect.disabled = true;

    if (seasonId) {
        await populateLeagues(seasonId);
    }

    updateStepStates();
    await updateCalendarUrl();
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
    elements.teamSelect.innerHTML = `<option value="">${t('filters.team.selectFirst')}</option>`;
    elements.teamSelect.disabled = true;

    if (groupId) {
        // Only needs groupId now - uses efficient /api/teams?group_id endpoint
        await populateTeams(groupId);
    }

    updateStepStates();
    await updateCalendarUrl();
    loadMatches();
}

// Team change handler
async function onTeamChange() {
    const teamId = elements.teamSelect.value;
    const teamOption = elements.teamSelect.selectedOptions[0];

    state.filters.team = teamId;
    state.filters.teamName = teamOption?.dataset.teamName || '';

    updateStepStates();
    await updateCalendarUrl();
    loadMatches();
}

// Mode change handler
async function onModeChange(event) {
    state.mode = event.target.checked ? 'player' : 'fan';

    // Show/hide prep time dropdown based on mode
    elements.prepTimeContainer.style.display = state.mode === 'player' ? 'block' : 'none';

    updateStepStates();
    await updateCalendarUrl();

    // Re-render matches to show/hide game time prefix
    if (state.matches.length > 0) {
        displayMatches(state.matches);
    }
}

// Prep time change handler
async function onPrepTimeChange() {
    state.prepHours = parseInt(elements.prepHoursSelect.value, 10);
    state.prepMinutes = parseInt(elements.prepMinutesSelect.value, 10);

    // Calculate total prep time in minutes
    state.prepTime = state.prepHours * 60 + state.prepMinutes;

    // Ensure minimum of 15 minutes when both are 0
    if (state.prepTime === 0) {
        state.prepMinutes = 15;
        elements.prepMinutesSelect.value = '15';
        state.prepTime = 15;
    }

    await updateCalendarUrl();

    // Re-render preview to show updated event start times
    if (state.matches.length > 0) {
        displayMatches(state.matches);
    }
}

// Time format change handler
async function onTimeFormatChange(event) {
    state.timeFormat = event.target.value;
    await updateCalendarUrl();

    // Re-render matches to show updated time format
    if (state.matches.length > 0) {
        displayMatches(state.matches);
    }
}

// Timezone change handler
async function onTimezoneChange(event) {
    state.timezone = event.target.value;
    await updateCalendarUrl();

    // Re-render matches to show updated timezone
    if (state.matches.length > 0) {
        displayMatches(state.matches);
    }
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

    // Step 4: Mode (always active once league is selected)
    const step4 = steps[3];
    if (step4) {
        step4.classList.remove('active', 'completed', 'disabled');
        if (!state.filters.league) {
            step4.classList.add('disabled');
        } else if (state.mode === 'player') {
            step4.classList.add('completed');
        } else {
            step4.classList.add('active');
        }
    }
}

// Load matches based on current filters
// Uses ID-based filtering (group_id, team_id) for better performance and stability
async function loadMatches() {
    // Require at least season and league selection
    if (!state.filters.season || !state.filters.league) {
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.selectFilters')}</p>`;
        elements.matchesCount.textContent = '';
        return;
    }

    elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.loading')}</p>`;

    try {
        const params = new URLSearchParams();
        params.set('season', state.filters.season);
        // Use ID-based filtering (preferred over name-based)
        params.set('group_id', state.filters.league);
        if (state.filters.team) {
            params.set('team_id', state.filters.team);
        }

        const matches = await fetchAPI(`/api/matches?${params.toString()}`);
        state.matches = matches || [];

        // Display all matches (no date filtering)
        displayMatches(state.matches);
    } catch (error) {
        console.error('Error loading matches:', error);
        elements.matchesPreview.innerHTML = `<p class="loading">${t('toast.matchError')}</p>`;
    }
}

// Display matches in preview
function displayMatches(matches) {
    if (matches.length === 0) {
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.noMatches')}</p>`;
        elements.matchesCount.textContent = '';
        return;
    }

    elements.matchesPreview.innerHTML = matches.slice(0, 100).map(match => {
        const home = match.homeTeam?.name || 'TBD';
        const away = match.awayTeam?.name || 'TBD';
        const gameTime = formatGameTime(match.date);
        const status = getStatusDisplay(match);
        const location = match.court?.place || '';

        // In player mode, event starts prep time before game
        // Calculate event start time and format accordingly
        let eventDate;
        if (state.mode === 'player' && match.date) {
            const gameDate = new Date(match.date);
            const eventStart = new Date(gameDate.getTime() - state.prepTime * 60 * 1000);
            eventDate = formatDate(eventStart.toISOString());
        } else {
            eventDate = formatDate(match.date);
        }

        // Build teams string with optional game time prefix for player mode
        let teams;
        if (match.status === 'CLOSED' && match.score?.totals) {
            const homeScore = getScore(match, 'home');
            const awayScore = getScore(match, 'away');
            // Use explicit score labels to avoid RTL confusion
            if (state.mode === 'player' && gameTime) {
                teams = `${gameTime} ${home} (${homeScore}) ${t('match.versus')} ${away} (${awayScore})`;
            } else {
                teams = `${home} (${homeScore}) ${t('match.versus')} ${away} (${awayScore})`;
            }
        } else {
            if (state.mode === 'player' && gameTime) {
                teams = `${gameTime} ${home} ${t('match.versus')} ${away}`;
            } else {
                teams = `${home} ${t('match.versus')} ${away}`;
            }
        }

        return `
            <div class="match-item">
                <div>
                    <div class="match-teams">${teams}</div>
                    <div class="match-meta">${eventDate}${location ? ' | ' + location : ''}</div>
                </div>
                <span class="match-status ${status.class}">${status.text}</span>
            </div>
        `;
    }).join('');

    elements.matchesCount.textContent = t('preview.showingCount', {
        shown: Math.min(matches.length, 100),
        total: matches.length
    });
}

// Format game time based on selected time format and timezone
function formatGameTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);

    const options = {
        hour: state.timeFormat === '12h' ? 'numeric' : '2-digit',
        minute: '2-digit',
        hour12: state.timeFormat === '12h',
        timeZone: state.timezone
    };

    return date.toLocaleTimeString(getLocale(), options);
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
            return { text: t('match.status.closed'), class: 'closed' };
        case 'LIVE':
            return { text: t('match.status.live'), class: 'live' };
        default:
            return { text: t('match.status.upcoming'), class: 'upcoming' };
    }
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString(getLocale(), {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Fetch calendar URLs from backend
// Backend handles URL construction and encoding for all platforms
async function fetchCalendarUrls() {
    const params = new URLSearchParams();

    if (state.filters.season) params.set('season', state.filters.season);
    if (state.filters.league) params.set('group_id', state.filters.league);
    if (state.filters.team) params.set('team_id', state.filters.team);

    // Add player mode parameters
    if (state.mode === 'player') {
        params.set('mode', 'player');
        params.set('prep', state.prepTime.toString());
        params.set('tf', state.timeFormat);
        params.set('tz', state.timezone);
    }

    try {
        return await fetchAPI(`/api/calendar-url?${params.toString()}`);
    } catch (error) {
        console.error('Error fetching calendar URLs:', error);
        return null;
    }
}

// Update calendar URL
// Uses backend-generated URLs for all platforms
async function updateCalendarUrl() {
    // Fetch URLs from backend
    const urls = await fetchCalendarUrls();

    if (urls) {
        state.calendarUrls = urls;

        // Update UI with backend-generated URLs
        elements.calendarUrl.value = urls.ics_url;
        elements.downloadLink.href = urls.ics_url.replace(window.location.origin, '');
        elements.googleLink.href = urls.google_url;
        elements.appleLink.href = urls.webcal_url;
        elements.outlook365Link.href = urls.outlook365_url;
        elements.outlookComLink.href = urls.outlook_url;
    } else {
        // Fallback: clear URLs if backend call fails
        state.calendarUrls = null;
        elements.calendarUrl.value = '';
    }
}

// Copy calendar URL to clipboard
async function copyCalendarUrl() {
    try {
        await navigator.clipboard.writeText(elements.calendarUrl.value);
        showToast(t('toast.copied'), 'success');
    } catch (error) {
        // Fallback for older browsers
        elements.calendarUrl.select();
        document.execCommand('copy');
        showToast(t('toast.copied'), 'success');
    }
}

// Refresh data with rate limiting support
async function refreshData() {
    elements.refreshBtn.disabled = true;
    elements.refreshBtn.textContent = t('footer.refreshing');

    try {
        // Start the background refresh
        const response = await fetch(API_BASE + '/api/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        // Handle different response statuses
        switch (result.status) {
            case 'rate_limited':
                showToast(
                    t('toast.rateLimited', { seconds: result.retry_after }),
                    'warning'
                );
                elements.refreshBtn.disabled = false;
                elements.refreshBtn.textContent = t('footer.refresh');
                return; // Don't poll, just return

            case 'in_progress':
                showToast(t('toast.refreshInProgress'), 'info');
                break;

            case 'started':
                showToast(t('toast.refreshStarted'), 'info');
                break;

            default:
                console.warn('Unknown refresh status:', result.status);
        }

        // Poll for completion
        await pollRefreshStatus();

        showToast(t('toast.refreshSuccess'), 'success');

        // Clear cached data and reload
        state.competitions = {};
        state.teams = {};

        await loadInitialData();

    } catch (error) {
        console.error('Error refreshing data:', error);
        showToast(t('toast.refreshError'), 'error');
    } finally {
        elements.refreshBtn.disabled = false;
        elements.refreshBtn.textContent = t('footer.refresh');
    }
}

// Poll refresh status until complete with timeout handling
async function pollRefreshStatus() {
    const maxAttempts = 30; // Max 10 minutes (18 * 20 seconds)
    let attempts = 0;

    while (attempts < maxAttempts) {
        await sleep(20000); // Wait 20 seconds between polls

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000);

            const response = await fetch(API_BASE + '/api/refresh-status', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            const status = await response.json();

            if (!status.is_scraping) {
                // Scraping is done - check if there was an error
                if (status.last_error) {
                    throw new Error(status.last_error);
                }
                return; // Success!
            }

            // Update button text with progress indicator
            const dots = '.'.repeat((attempts % 3) + 1);
            elements.refreshBtn.textContent = t('footer.refreshing').replace('...', '') + dots;

            attempts++;

        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('Poll request timed out, continuing...');
                attempts++;
                continue;
            }
            throw error;
        }
    }

    // Timeout after max attempts
    throw new Error(t('toast.refreshTimeout'));
}

// Sleep helper
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Update cache status display
function updateCacheStatus(cacheInfo) {
    lastCacheInfo = cacheInfo;
    const labelEl = document.querySelector('.last-updated-label');
    const timeEl = elements.lastUpdate;

    if (!cacheInfo || !cacheInfo.exists) {
        labelEl.textContent = '';
        timeEl.textContent = t('footer.noData');
        timeEl.classList.add('warning');
        return;
    }

    if (cacheInfo.stale) {
        labelEl.textContent = '';
        timeEl.textContent = t('footer.staleData');
        timeEl.classList.add('warning');
        return;
    }

    // Fresh data - show last updated time
    labelEl.textContent = t('footer.lastUpdated');
    timeEl.classList.remove('warning');
    const date = new Date(cacheInfo.last_updated);
    timeEl.textContent = date.toLocaleString(getLocale());
}

// Show toast notification
function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type} show`;

    setTimeout(() => {
        elements.toast.className = 'toast';
    }, 3000);
}

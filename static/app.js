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
    }
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

    // Initialize tabs and player search (after i18next is ready)
    initTabs();
    initPlayerSearch();
});

// Listen for language changes to update dynamic content
window.addEventListener('languageChanged', () => {
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

    // Update player search placeholder
    const playerSearchInput = document.getElementById('player-search');
    if (playerSearchInput) {
        playerSearchInput.placeholder = t('player.placeholder');
    }
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
        updateCalendarUrl();

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
async function populateTeams(groupId, competitionName) {
    elements.teamSelect.innerHTML = `<option value="">${t('filters.team.loading')}</option>`;
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
    elements.teamSelect.innerHTML = `<option value="">${t('filters.team.selectFirst')}</option>`;
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
        elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.selectFilters')}</p>`;
        elements.matchesCount.textContent = '';
        return;
    }

    elements.matchesPreview.innerHTML = `<p class="loading">${t('preview.loading')}</p>`;

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
        const date = formatDate(match.date);
        const status = getStatusDisplay(match);
        const location = match.court?.place || '';

        let teams = `${home} ${t('match.versus')} ${away}`;
        if (match.status === 'CLOSED' && match.score?.totals) {
            const homeScore = getScore(match, 'home');
            const awayScore = getScore(match, 'away');
            // Use explicit score labels to avoid RTL confusion
            teams = `${home} (${homeScore}) ${t('match.versus')} ${away} (${awayScore})`;
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

    elements.matchesCount.textContent = t('preview.showingCount', {
        shown: Math.min(matches.length, 100),
        total: matches.length
    });
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

    // webcal:// protocol URL (used by multiple calendar apps)
    const webcalUrl = fullUrl.replace(/^https?:\/\//, 'webcal://');

    // Google Calendar subscribe URL
    const googleUrl = `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcalUrl)}`;
    elements.googleLink.href = googleUrl;

    // Apple Calendar - direct webcal:// link
    elements.appleLink.href = webcalUrl;

    // Build calendar name for Outlook
    const calendarNameParts = [t('header.title')];
    if (state.filters.leagueName) calendarNameParts.push(state.filters.leagueName);
    if (state.filters.teamName) calendarNameParts.push(state.filters.teamName);
    const calendarName = calendarNameParts.join(' - ');

    // Outlook 365 (work/school)
    const outlook365Url = `https://outlook.office.com/calendar/0/addfromweb?url=${encodeURIComponent(webcalUrl)}&name=${encodeURIComponent(calendarName)}`;
    elements.outlook365Link.href = outlook365Url;

    // Outlook.com (personal)
    const outlookComUrl = `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(webcalUrl)}&name=${encodeURIComponent(calendarName)}`;
    elements.outlookComLink.href = outlookComUrl;
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

// ============================================
// TAB NAVIGATION
// ============================================

// Initialize tabs
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            switchTab(tabId);
        });
    });
}

// Switch to a specific tab
function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `${tabId}-tab`);
    });
}

// ============================================
// PLAYER SEARCH
// ============================================

// Player state
let playerState = {
    searchTimeout: null,
    currentPlayer: null,
    spLeagues: {},  // SportsPress leagues lookup
    spTeams: {}     // SportsPress teams lookup
};

// Player DOM elements (lazy init)
let playerElements = null;

function getPlayerElements() {
    if (!playerElements) {
        playerElements = {
            searchInput: document.getElementById('player-search'),
            suggestions: document.getElementById('player-suggestions'),
            details: document.getElementById('player-details'),
            playerName: document.getElementById('player-name'),
            currentTeams: document.getElementById('player-current-teams'),
            pastTeams: document.getElementById('player-past-teams'),
            leaguesList: document.getElementById('player-leagues-list'),
            statsSeasonSelect: document.getElementById('stats-season-select'),
            statsBody: document.getElementById('player-stats-body'),
            noStatsMessage: document.getElementById('no-stats-message'),
            refreshPlayersBtn: document.getElementById('refresh-players-btn'),
            modal: document.getElementById('calendar-modal'),
            modalTitle: document.getElementById('modal-title'),
            modalTeamName: document.getElementById('modal-team-name'),
            modalGoogleLink: document.getElementById('modal-google-link'),
            modalAppleLink: document.getElementById('modal-apple-link'),
            modalDownloadLink: document.getElementById('modal-download-link')
        };
    }
    return playerElements;
}

// Initialize player search functionality
function initPlayerSearch() {
    const el = getPlayerElements();
    if (!el.searchInput) return;

    // Search input with debounce
    el.searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Clear previous timeout
        if (playerState.searchTimeout) {
            clearTimeout(playerState.searchTimeout);
        }

        // Hide suggestions if query is too short
        if (query.length < 2) {
            el.suggestions.classList.remove('show');
            return;
        }

        // Debounce search
        playerState.searchTimeout = setTimeout(() => {
            searchPlayers(query);
        }, 300);
    });

    // Close suggestions when clicking outside
    document.addEventListener('click', (e) => {
        if (!el.searchInput.contains(e.target) && !el.suggestions.contains(e.target)) {
            el.suggestions.classList.remove('show');
        }
    });

    // Stats season selector change
    el.statsSeasonSelect.addEventListener('change', () => {
        if (playerState.currentPlayer) {
            displayPlayerStatistics(playerState.currentPlayer.statistics);
        }
    });

    // Refresh players button
    el.refreshPlayersBtn.addEventListener('click', refreshPlayerData);

    // Set placeholder
    el.searchInput.placeholder = t('player.placeholder');
}

// Search for players
async function searchPlayers(query) {
    const el = getPlayerElements();

    try {
        const players = await fetchAPI(`/api/players?q=${encodeURIComponent(query)}&limit=20`);

        if (players.length === 0) {
            el.suggestions.innerHTML = `<div class="no-results">${t('player.noResults')}</div>`;
            el.suggestions.classList.add('show');
            return;
        }

        el.suggestions.innerHTML = players.map(player => {
            const teamsText = player.current_teams?.length
                ? `${player.current_teams.length} ${t('player.teams').toLowerCase()}`
                : '';

            return `
                <div class="suggestion-item" onclick="selectPlayer(${player.id})">
                    <div class="player-name">${escapeHtml(player.name)}</div>
                    ${teamsText ? `<div class="player-teams">${teamsText}</div>` : ''}
                </div>
            `;
        }).join('');

        el.suggestions.classList.add('show');

    } catch (error) {
        console.error('Error searching players:', error);
        el.suggestions.innerHTML = `<div class="no-results">${t('toast.loadError')}</div>`;
        el.suggestions.classList.add('show');
    }
}

// Select a player
async function selectPlayer(playerId) {
    const el = getPlayerElements();

    // Hide suggestions
    el.suggestions.classList.remove('show');
    el.searchInput.value = '';

    // Show loading state with spinner
    el.details.classList.remove('hidden');
    el.playerName.textContent = t('player.loading');
    el.currentTeams.innerHTML = '<p class="loading-spinner">⏳</p>';
    el.pastTeams.innerHTML = '<p class="loading-spinner">⏳</p>';
    el.leaguesList.innerHTML = '<li class="loading-spinner">⏳</li>';
    el.statsBody.innerHTML = '<tr><td colspan="9" class="loading-spinner">⏳ ' + t('player.loadingStats') + '</td></tr>';
    el.noStatsMessage.classList.add('hidden');

    try {
        // Load SP lookup data if not already loaded (for stats display)
        await loadSPLookupData();

        // Fetch player details with stats (on-demand from SportsPress API)
        // This may take 1-2 seconds as it fetches fresh stats
        const player = await fetchAPI(`/api/players/${playerId}`, { timeout: 15000 });
        playerState.currentPlayer = player;

        displayPlayerDetails(player);

    } catch (error) {
        console.error('Error loading player:', error);
        el.playerName.textContent = t('toast.loadError');
        el.currentTeams.innerHTML = '';
        el.pastTeams.innerHTML = '';
        el.leaguesList.innerHTML = '';
        el.statsBody.innerHTML = '';
        el.noStatsMessage.textContent = t('player.statsUnavailable');
        el.noStatsMessage.classList.remove('hidden');
    }
}

// Load SportsPress lookup data (teams and leagues)
async function loadSPLookupData() {
    if (Object.keys(playerState.spLeagues).length === 0) {
        const leagues = await fetchAPI('/api/sp-leagues');
        leagues.forEach(lg => {
            playerState.spLeagues[lg.id] = lg;
        });
    }

    if (Object.keys(playerState.spTeams).length === 0) {
        const teams = await fetchAPI('/api/sp-teams');
        teams.forEach(t => {
            playerState.spTeams[t.id] = t;
        });
    }
}

// Display player details
function displayPlayerDetails(player) {
    const el = getPlayerElements();

    // Get player name
    const name = player.title?.rendered || player.name || 'Unknown';
    el.playerName.textContent = name;

    // Display teams
    displayPlayerTeams(player);

    // Display leagues
    displayPlayerLeagues(player);

    // Display statistics
    populateStatsSeasonSelector(player.statistics);
    displayPlayerStatistics(player.statistics);
}

// Display player teams
function displayPlayerTeams(player) {
    const el = getPlayerElements();

    // Current teams - use pre-resolved _current_teams from API
    const currentTeams = player._current_teams || [];
    if (currentTeams.length > 0) {
        el.currentTeams.innerHTML = currentTeams.map(team => {
            return createTeamCard(team);
        }).join('');
    } else {
        el.currentTeams.innerHTML = `<p class="no-teams">${t('player.noTeams')}</p>`;
    }

    // Past teams - use pre-resolved _past_teams from API
    const pastTeams = player._past_teams || [];
    if (pastTeams.length > 0) {
        el.pastTeams.innerHTML = pastTeams.map(team => {
            return createTeamCard(team);
        }).join('');
    } else {
        el.pastTeams.innerHTML = `<p class="no-teams">${t('player.noTeams')}</p>`;
    }
}

// Create a team card HTML
function createTeamCard(team) {
    return `
        <div class="team-card">
            <div class="team-info">
                <span class="team-name">${escapeHtml(team.name)}</span>
            </div>
            <button class="btn btn-primary btn-subscribe" onclick="openCalendarModal('${escapeHtml(team.name)}')">
                ${t('player.subscribeTeam')}
            </button>
        </div>
    `;
}

// Display player leagues
function displayPlayerLeagues(player) {
    const el = getPlayerElements();

    // Use pre-resolved _leagues from API
    const leagues = player._leagues || [];
    if (leagues.length > 0) {
        el.leaguesList.innerHTML = leagues.map(league => {
            return `<li>${escapeHtml(league.name)}</li>`;
        }).join('');
    } else {
        el.leaguesList.innerHTML = `<li class="no-teams">${t('player.noTeams')}</li>`;
    }
}

// Populate stats season selector
function populateStatsSeasonSelector(statistics) {
    const el = getPlayerElements();

    if (!statistics || Object.keys(statistics).length === 0) {
        el.statsSeasonSelect.innerHTML = `<option value="">-</option>`;
        return;
    }

    // Get all unique league-season combinations
    const options = [];

    Object.entries(statistics).forEach(([leagueId, seasonData]) => {
        const league = playerState.spLeagues[leagueId] || { name: `League ${leagueId}` };

        Object.keys(seasonData).forEach(seasonKey => {
            // Skip special keys
            if (seasonKey === '0' || seasonKey === '-1') return;

            options.push({
                value: `${leagueId}:${seasonKey}`,
                label: league.name
            });
        });
    });

    if (options.length === 0) {
        el.statsSeasonSelect.innerHTML = `<option value="">-</option>`;
        return;
    }

    el.statsSeasonSelect.innerHTML = options.map((opt, idx) =>
        `<option value="${opt.value}" ${idx === 0 ? 'selected' : ''}>${escapeHtml(opt.label)}</option>`
    ).join('');
}

// Display player statistics
function displayPlayerStatistics(statistics) {
    const el = getPlayerElements();

    if (!statistics || Object.keys(statistics).length === 0) {
        el.statsBody.innerHTML = '';
        el.noStatsMessage.classList.remove('hidden');
        return;
    }

    // Get selected league:season
    const selected = el.statsSeasonSelect.value;
    if (!selected) {
        el.statsBody.innerHTML = '';
        el.noStatsMessage.classList.remove('hidden');
        return;
    }

    const [leagueId, seasonKey] = selected.split(':');
    const seasonData = statistics[leagueId]?.[seasonKey];

    if (!seasonData) {
        el.statsBody.innerHTML = '';
        el.noStatsMessage.classList.remove('hidden');
        return;
    }

    el.noStatsMessage.classList.add('hidden');

    // Extract stats (handling both number and string values)
    const getValue = (key) => {
        const val = seasonData[key];
        if (val === undefined || val === null || val === '') return '-';
        return val;
    };

    // Calculate total rebounds
    const rebOff = parseInt(seasonData.off) || 0;
    const rebDef = parseInt(seasonData.def) || 0;
    const totalReb = rebOff + rebDef || getValue('reb');

    el.statsBody.innerHTML = `
        <tr>
            <td>${getValue('g')}</td>
            <td>${getValue('mins')}</td>
            <td>${getValue('pts')}</td>
            <td>${totalReb}</td>
            <td>${getValue('ast')}</td>
            <td>${getValue('stl')}</td>
            <td>${getValue('blk')}</td>
            <td>${getValue('to')}</td>
            <td>${getValue('eff')}</td>
        </tr>
    `;
}

// Refresh player data
async function refreshPlayerData() {
    const el = getPlayerElements();

    el.refreshPlayersBtn.disabled = true;
    el.refreshPlayersBtn.textContent = t('player.refreshing');

    try {
        const response = await fetch(API_BASE + '/api/players/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        if (result.status === 'started') {
            showToast(t('toast.refreshStarted'), 'info');
        } else if (result.status === 'in_progress') {
            showToast(t('toast.refreshInProgress'), 'info');
        }

        // Clear cached lookup data
        playerState.spLeagues = {};
        playerState.spTeams = {};

    } catch (error) {
        console.error('Error refreshing player data:', error);
        showToast(t('toast.refreshError'), 'error');
    } finally {
        el.refreshPlayersBtn.disabled = false;
        el.refreshPlayersBtn.textContent = t('player.refresh');
    }
}

// ============================================
// CALENDAR SUBSCRIPTION MODAL
// ============================================

// Open calendar subscription modal
function openCalendarModal(teamName) {
    const el = getPlayerElements();

    el.modalTitle.textContent = t('player.subscribeTitle', { team: teamName });
    el.modalTeamName.textContent = teamName;

    // Generate calendar URL for this team
    const baseUrl = window.location.origin;
    const calendarPath = `/calendar.ics?team=${encodeURIComponent(teamName)}`;
    const fullUrl = `${baseUrl}${calendarPath}`;
    const webcalUrl = fullUrl.replace(/^https?:\/\//, 'webcal://');

    // Set up links
    el.modalGoogleLink.href = `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcalUrl)}`;
    el.modalAppleLink.href = webcalUrl;
    el.modalDownloadLink.href = calendarPath;

    // Show modal
    el.modal.classList.remove('hidden');
}

// Close calendar subscription modal
function closeCalendarModal() {
    const el = getPlayerElements();
    el.modal.classList.add('hidden');
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('calendar-modal');
    if (modal && e.target === modal) {
        closeCalendarModal();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeCalendarModal();
    }
});

// ============================================
// UTILITY FUNCTIONS
// ============================================

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


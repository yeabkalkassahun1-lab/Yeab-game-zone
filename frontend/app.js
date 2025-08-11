document.addEventListener('DOMContentLoaded', () => {
    // --- Initialize Telegram & Basic Setup ---
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    // --- DOM Element References ---
    const getEl = id => document.getElementById(id);
    const loadingScreen = getEl('loading-screen');
    const mainApp = getEl('main-app');
    const statusIndicator = getEl('status-indicator');
    const statusText = getEl('status-text');
    const gameListContainer = getEl('game-list-container');
    const newGameBtn = getEl('new-game-btn');
    const filtersContainer = document.querySelector('.filters');
    const stakeModal = getEl('stake-modal');
    const closeStakeModalBtn = getEl('close-stake-modal-btn');
    const stakeOptionsGrid = getEl('stake-options-grid');
    const cancelStakeBtn = getEl('cancel-stake-btn');
    const nextStakeBtn = getEl('next-stake-btn');
    const confirmModal = getEl('confirm-modal');
    const closeConfirmModalBtn = getEl('close-confirm-modal-btn');
    const winConditionOptions = getEl('win-condition-options');
    const createGameBtn = getEl('create-game-btn');
    const cancelConfirmBtn = getEl('cancel-confirm-btn');
    const summaryStakeAmount = getEl('summary-stake-amount');
    const summaryPrizeAmount = getEl('summary-prize-amount');

    // --- Application State ---
    let socket = null;
    let allGames = [];
    let isConnected = false;

    // --- Central Validation Logic for Create Button ---
    const validateCreateButtonState = () => {
        const selectedStake = stakeOptionsGrid.querySelector('.selected');
        const selectedWinCondition = winConditionOptions.querySelector('.selected');
        createGameBtn.disabled = !(selectedStake && selectedWinCondition && isConnected);
    };

    // --- UI Update Functions ---
    const updateConnectionStatus = (status, text) => {
        statusIndicator.className = status;
        statusText.textContent = text;
    };

    // --- WebSocket Logic ---
    function connectWebSocket() {
        updateConnectionStatus('connecting', 'Connecting...');
        const userId = tg.initDataUnsafe?.user?.id || '123456789'; // Fallback for testing in browser

        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socketURL = `${proto}//${window.location.host}/ws/${userId}`;
        
        socket = new WebSocket(socketURL);

        socket.onopen = () => {
            isConnected = true;
            updateConnectionStatus('connected', 'Connected');
            validateCreateButtonState();
        };

        socket.onclose = () => {
            isConnected = false;
            updateConnectionStatus('disconnected', 'Disconnected');
            validateCreateButtonState();
            setTimeout(connectWebSocket, 5000); // Retry connection after 5 seconds
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
            isConnected = false;
            updateConnectionStatus('disconnected', 'Failed');
            validateCreateButtonState();
            socket.close();
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Switch statement to handle different real-time events from the server
                switch (data.event) {
                    case "initial_game_list":
                        allGames = data.games;
                        applyCurrentFilter();
                        break;
                    case "new_game":
                        if (!allGames.some(g => g.id === data.game.id)) {
                            allGames.unshift(data.game);
                        }
                        applyCurrentFilter();
                        break;
                    case "remove_game":
                        allGames = allGames.filter(g => g.id !== data.gameId);
                        removeGameCard(data.gameId);
                        break;
                    case "balance_update":
                         getEl('balance-amount').textContent = parseFloat(data.balance).toFixed(2);
                         break;
                }
            } catch (e) {
                console.error("Failed to parse incoming WebSocket message:", e);
            }
        };
    }
    
    // --- UI Rendering ---
    const getWinConditionText = c => ({1:"1 Token Home", 2:"2 Tokens Home", 4:"4 Tokens Home"}[c] || `${c} Piece`);

    function renderGameList(games) {
        gameListContainer.innerHTML = '';
        if (games.length === 0) {
            gameListContainer.innerHTML = `<h3 class="empty-state-title">No Open Games</h3><p class="empty-state-subtitle">Why not create one?</p>`;
            return;
        }
        games.forEach(addGameCard);
    }

    function addGameCard(game) {
        const card = document.createElement('div');
        card.className = 'game-card';
        card.id = `game-${game.id}`;
        card.innerHTML = `
            <div class="gc-player-info">
                <div class="gc-avatar">🧙</div>
                <div class="gc-name-stake">
                    <span class="gc-name">${game.creatorName || 'Anonymous'}</span>
                    <span class="gc-stake">${game.stake.toFixed(2)} ETB</span>
                </div>
            </div>
            <div class="gc-win-condition">
                <span class="gc-icon">🏆</span>
                <span class="gc-text">${getWinConditionText(game.win_condition)}</span>
            </div>
            <div class="gc-actions">
                <span class="gc-prize-label">Prize</span>
                <span class="gc-prize">${game.prize.toFixed(2)} ETB</span>
                <button class="gc-join-btn" data-game-id="${game.id}">Join</button>
            </div>`;
        gameListContainer.appendChild(card);
    }

    function removeGameCard(id) {
        const card = document.getElementById(`game-${id}`);
        if (card) card.remove();
        if (gameListContainer.children.length === 0) {
            renderGameList([]); // Re-render to show empty state
        }
    }
    
    // --- Filter Logic ---
    function applyCurrentFilter() {
        const activeFilterBtn = filtersContainer.querySelector('.active');
        if (!activeFilterBtn) return;
        const filter = activeFilterBtn.dataset.filter;
        let filteredGames;
        if (filter === 'all') {
            filteredGames = allGames;
        } else if (filter.includes('-')) {
            const [min, max] = filter.split('-').map(Number);
            filteredGames = allGames.filter(g => g.stake >= min && g.stake <= max);
        } else {
            const min = Number(filter);
            filteredGames = allGames.filter(g => g.stake >= min);
        }
        renderGameList(filteredGames);
    }
    
    // --- Event Listeners ---
    function setupEventListeners() {
        filtersContainer.addEventListener('click', e => {
            const button = e.target.closest('.filter-button');
            if (!button) return;
            filtersContainer.querySelector('.active')?.classList.remove('active');
            button.classList.add('active');
            applyCurrentFilter();
        });

        newGameBtn.addEventListener('click', () => showModal(stakeModal));
        closeStakeModalBtn.addEventListener('click', () => hideModal(stakeModal));
        cancelStakeBtn.addEventListener('click', () => hideModal(stakeModal));
        nextStakeBtn.addEventListener('click', () => { hideModal(stakeModal); updateSummary(); showModal(confirmModal); });
        
        closeConfirmModalBtn.addEventListener('click', () => hideModal(confirmModal));
        cancelConfirmBtn.addEventListener('click', () => hideModal(confirmModal));

        stakeOptionsGrid.addEventListener('click', e => {
            const button = e.target.closest('.option-btn');
if (button) {
                stakeOptionsGrid.querySelector('.selected')?.classList.remove('selected');
                button.classList.add('selected');
                nextStakeBtn.disabled = false;
                updateSummary(); // Update summary as soon as stake is chosen
            }
        });

        winConditionOptions.addEventListener('click', e => {
            const button = e.target.closest('.win-option-btn');
            if (button) {
                winConditionOptions.querySelector('.selected')?.classList.remove('selected');
                button.classList.add('selected');
                validateCreateButtonState();
            }
        });

        createGameBtn.addEventListener('click', () => {
            if (createGameBtn.disabled) return;
            const selectedStakeEl = stakeOptionsGrid.querySelector('.selected');
            const selectedWinEl = winConditionOptions.querySelector('.selected');
            if (!socket || !selectedStakeEl || !selectedWinEl) return;
            
            socket.send(JSON.stringify({
                event: "create_game",
                payload: {
                    stake: parseInt(selectedStakeEl.dataset.stake, 10),
                    winCondition: parseInt(selectedWinEl.dataset.win, 10)
                }
            }));
            hideModal(confirmModal);
        });

        // Event delegation for joining games
        gameListContainer.addEventListener('click', e => {
            const joinBtn = e.target.closest('.gc-join-btn');
            if (joinBtn && socket) {
                const gameId = joinBtn.dataset.gameId;
                socket.send(JSON.stringify({ event: "join_game", payload: { gameId: gameId } }));
                tg.close(); // Close the web app to go back to the chat
            }
        });
    }

    const showModal = modal => {
        modal.classList.remove('hidden');
        setTimeout(() => {
            mainApp.style.filter = 'blur(5px)';
            modal.classList.add('active');
        }, 10);
    };

    const hideModal = modal => {
        mainApp.style.filter = 'none';
        modal.classList.remove('active');
        setTimeout(() => modal.classList.add('hidden'), 300);
    };
    
    function updateSummary() {
        const selectedStakeEl = stakeOptionsGrid.querySelector('.selected');
        if (!selectedStakeEl) return;
        const stake = parseInt(selectedStakeEl.dataset.stake, 10);
        const prize = (stake * 2) * 0.9;
        summaryStakeAmount.textContent = `Stake: ${stake} ETB`;
        summaryPrizeAmount.textContent = `${prize.toFixed(2)} ETB`;
    }

    // --- Failsafe Startup Sequence ---
    function init() {
        setTimeout(() => {
            loadingScreen.style.opacity = '0';
            mainApp.classList.remove('hidden');
            setTimeout(() => loadingScreen.remove(), 500);
            connectWebSocket();
        }, 1500);
        setupEventListeners();
        validateCreateButtonState();
    }
    
    init();
});
document.addEventListener('DOMContentLoaded', () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/progress`;

    const elBadge = document.getElementById('global-status-badge');
    const elStatusText = document.getElementById('global-status-text');
    const elCardMonth = document.getElementById('card-current-month');
    const elCardLastRun = document.getElementById('card-last-run');
    const elCardFiles = document.getElementById('card-files-progress');
    const elCardCurrentFile = document.getElementById('card-current-file');
    const elCardPgRows = document.getElementById('card-pg-rows');
    const elCardOracleRows = document.getElementById('card-oracle-rows');
    const elCardOracleTable = document.getElementById('card-oracle-table');

    const stepReceita = document.getElementById('step-receita');
    const stepPostgres = document.getElementById('step-postgres');
    const stepOracle = document.getElementById('step-oracle');
    const conn1 = document.getElementById('conn-1');
    const conn2 = document.getElementById('conn-2');

    const progressLabel = document.getElementById('progress-label');
    const progressPercent = document.getElementById('progress-percent');
    const mainProgressBar = document.getElementById('main-progress-bar');

    const selectMonth = document.getElementById('select-month');
    const checkForce = document.getElementById('check-force');
    const triggerForm = document.getElementById('trigger-form');
    const btnTrigger = document.getElementById('btn-trigger');

    const terminalBody = document.getElementById('terminal-body');
    const btnClearLog = document.getElementById('btn-clear-log');

    let ws = null;

    function appendLog(message, type = 'INFO') {
        const line = document.createElement('div');
        line.className = `log-line ${type}`;
        line.textContent = message;
        terminalBody.appendChild(line);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    btnClearLog.addEventListener('click', () => {
        terminalBody.innerHTML = '';
    });

    // Load available months
    async function loadMonths() {
        try {
            const res = await fetch('/api/months');
            const data = await res.json();
            if (data.available_months && data.available_months.length > 0) {
                selectMonth.innerHTML = '<option value="">Mês Mais Recente (Automático)</option>';
                data.available_months.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    selectMonth.appendChild(opt);
                });
            }
        } catch (e) {
            console.error('Erro ao carregar meses:', e);
        }
    }

    // Connect WebSocket
    function connectWS() {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            elStatusText.textContent = 'CONECTADO';
            elBadge.className = 'status-badge active-idle';
            appendLog('[WS] Conectado ao servidor em tempo real.');
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'status') {
                updateUI(msg.data);
            } else if (msg.type === 'log') {
                appendLog(msg.message);
            }
        };

        ws.onclose = () => {
            elStatusText.textContent = 'DESCONECTADO';
            elBadge.className = 'status-badge';
            appendLog('[WS] Conexão encerrada. Reconectando em 3s...');
            setTimeout(connectWS, 3000);
        };
    }

    function updateUI(status) {
        const state = status.state || 'IDLE';

        elStatusText.textContent = state;
        elBadge.className = 'status-badge';

        if (state === 'IDLE') {
            elBadge.classList.add('active-idle');
            btnTrigger.disabled = false;
        } else if (state === 'COMPLETED') {
            elBadge.classList.add('active-completed');
            btnTrigger.disabled = false;
        } else if (state === 'ERROR') {
            elBadge.classList.add('active-error');
            btnTrigger.disabled = false;
        } else {
            elBadge.classList.add('active-running');
            btnTrigger.disabled = true;
        }

        elCardMonth.textContent = status.current_month || '--';
        if (status.last_run) {
            elCardLastRun.textContent = `Última execução: ${status.last_run}`;
        }

        const filesTotal = status.files_total || 0;
        const filesProc = status.files_processed || 0;
        const filesPct = filesTotal > 0 ? Math.round((filesProc / filesTotal) * 100) : 0;
        elCardFiles.textContent = `${filesProc} / ${filesTotal} (${filesPct}%)`;
        elCardCurrentFile.textContent = status.current_file ? `Processando: ${status.current_file}` : 'Nenhum arquivo ativo';

        elCardPgRows.textContent = (status.current_rows || 0).toLocaleString('pt-BR');
        elCardOracleRows.textContent = (status.oracle_rows || 0).toLocaleString('pt-BR');
        elCardOracleTable.textContent = status.oracle_current_table ? `Tabela: ${status.oracle_current_table}` : 'Tabela: --';

        // Stepper & Progress logic
        stepReceita.classList.remove('active', 'completed');
        stepPostgres.classList.remove('active', 'completed');
        stepOracle.classList.remove('active', 'completed');
        conn1.classList.remove('active');
        conn2.classList.remove('active');

        let pct = 0;

        if (state === 'CHECKING' || state === 'DOWNLOADING') {
            stepReceita.classList.add('active');
            progressLabel.textContent = `Baixando arquivos da Receita Federal (${filesPct}%)...`;
            pct = filesTotal > 0 ? Math.round((filesProc / filesTotal) * 33) : 10;
        } else if (state === 'PROCESSING_PG') {
            stepReceita.classList.add('completed');
            conn1.classList.add('active');
            stepPostgres.classList.add('active');
            progressLabel.textContent = `Inserindo no PostgreSQL: ${status.current_file || ''} (${filesPct}%)`;
            pct = 33 + (filesTotal > 0 ? Math.round((filesProc / filesTotal) * 33) : 0);
        } else if (state === 'MIGRATING_ORACLE') {
            stepReceita.classList.add('completed');
            stepPostgres.classList.add('completed');
            conn1.classList.add('active');
            conn2.classList.add('active');
            stepOracle.classList.add('active');
            progressLabel.textContent = `Migrando para o Oracle DB (${status.oracle_current_table || ''})...`;
            pct = 75;
        } else if (state === 'COMPLETED') {
            stepReceita.classList.add('completed');
            stepPostgres.classList.add('completed');
            stepOracle.classList.add('completed');
            conn1.classList.add('active');
            conn2.classList.add('active');
            progressLabel.textContent = 'Pipeline concluída com sucesso!';
            pct = 100;
        }

        mainProgressBar.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}%`;

        // Update zip files table
        if (status.file_statuses) {
            renderFilesTable(status.file_statuses);
        }
    }

    function renderFilesTable(fileStatuses) {
        const tbody = document.getElementById('files-table-body');
        const countBadge = document.getElementById('table-files-count');
        const files = Object.values(fileStatuses);

        countBadge.textContent = `${files.length} arquivo(s)`;

        if (files.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-row">Nenhum arquivo encontrado para o mês selecionado.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        files.forEach(f => {
            const tr = document.createElement('tr');

            let badgeClass = 'status-pending';
            let badgeText = 'Pendente (0%)';
            let badgeIcon = '⏸️';

            if (f.status === 'COMPLETED') {
                badgeClass = 'status-completed';
                badgeText = 'Concluído (100%)';
                badgeIcon = '✅';
            } else if (f.status === 'DOWNLOADING') {
                badgeClass = 'status-processing';
                const dlPct = f.download_pct !== undefined ? f.download_pct.toFixed(1) : 0;
                badgeText = `Baixando (${dlPct}%)`;
                badgeIcon = '⏳';
            } else if (f.status === 'PROCESSING_PG') {
                badgeClass = 'status-processing';
                badgeText = 'Inserindo PG';
                badgeIcon = '⚡';
            } else if (f.status === 'ERROR') {
                badgeClass = 'status-error';
                badgeText = 'Erro';
                badgeIcon = '❌';
            }

            const infoCell = f.error
                ? `<span class="error-detail">Erro: ${f.error}</span>`
                : `${(f.rows || 0).toLocaleString('pt-BR')} registros`;

            tr.innerHTML = `
                <td class="file-name-cell">${f.filename}</td>
                <td><strong>${f.file_type || '--'}</strong></td>
                <td><span class="badge-file-status ${badgeClass}">${badgeIcon} ${badgeText}</span></td>
                <td>${infoCell}</td>
            `;

            tbody.appendChild(tr);
        });
    }

    // Submit Trigger
    triggerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const selectedMonth = selectMonth.value;
        const force = checkForce.checked;

        btnTrigger.disabled = true;

        try {
            const res = await fetch('/api/trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ month: selectedMonth || null, force: force })
            });

            const data = await res.json();
            appendLog(`[TRIGGER] ${data.message}`);
        } catch (err) {
            appendLog(`[ERRO] Falha ao disparar pipeline: ${err}`, 'ERROR');
            btnTrigger.disabled = false;
        }
    });

    loadMonths();
    connectWS();
});

let allReports = [];
let currentReportId = null;

async function loadReports() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value.trim();
    
    if (!token) {
        alert("請輸入管理金鑰！");
        return;
    }

    const reportList = document.getElementById('report-list');
    const loginOverlay = document.getElementById('login-overlay');
    const dashboardContent = document.getElementById('dashboard-content');
    
    reportList.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>正在同步伺服器資料...</p>
        </div>
    `;

    try {
        const response = await fetch('/admin/reports', {
            headers: { 'token': token }
        });

        if (response.status === 401) {
            alert("金鑰錯誤，請重新輸入。");
            return;
        }

        if (!response.ok) throw new Error("網路錯誤");

        allReports = await response.json();
        
        // Also fetch monitored buses
        try {
            const busesRes = await fetch('/admin/monitored_buses', {
                headers: { 'token': token }
            });
            if (busesRes.ok) {
                monitoredBuses = await busesRes.json();
            }
        } catch (e) {
            console.error("Failed to load monitored buses at startup:", e);
        }

        // Restore type filter checkbox states from localStorage
        restoreTypeFilterState();
        
        // Success: Hide login, show dashboard
        loginOverlay.classList.add('hidden');
        dashboardContent.classList.remove('hidden');
        
        renderReports();
        updateStats();
    } catch (error) {
        console.error(error);
        alert("連線失敗，請檢查網路狀態。");
    }
}

let hideDone = false;

function toggleHideDone() {
    hideDone = document.getElementById('hide-done-check').checked;
    renderReports();
}

function saveTypeFilterState() {
    if (document.getElementById('filter-type-replace')) {
        localStorage.setItem('report_type_filter_replace', document.getElementById('filter-type-replace').checked);
        localStorage.setItem('report_type_filter_repair', document.getElementById('filter-type-repair').checked);
        localStorage.setItem('report_type_filter_design', document.getElementById('filter-type-design').checked);
        localStorage.setItem('report_type_filter_other', document.getElementById('filter-type-other').checked);
    }
}

function restoreTypeFilterState() {
    if (document.getElementById('filter-type-replace')) {
        document.getElementById('filter-type-replace').checked = localStorage.getItem('report_type_filter_replace') !== 'false';
        document.getElementById('filter-type-repair').checked = localStorage.getItem('report_type_filter_repair') !== 'false';
        document.getElementById('filter-type-design').checked = localStorage.getItem('report_type_filter_design') !== 'false';
        document.getElementById('filter-type-other').checked = localStorage.getItem('report_type_filter_other') !== 'false';
    }
}

function renderReports() {
    const list = document.getElementById('report-list');
    list.innerHTML = '';

    const showReplace = document.getElementById('filter-type-replace') ? document.getElementById('filter-type-replace').checked : true;
    const showRepair = document.getElementById('filter-type-repair') ? document.getElementById('filter-type-repair').checked : true;
    const showDesign = document.getElementById('filter-type-design') ? document.getElementById('filter-type-design').checked : true;
    const showOther = document.getElementById('filter-type-other') ? document.getElementById('filter-type-other').checked : true;

    const filteredReports = allReports.filter(r => {
        // Status filter
        if (hideDone && r.status === '已完成') return false;
        
        // Type filter
        const type = r.solution_type;
        if (type === '更換') return showReplace;
        if (type === '維修') return showRepair;
        if (type === '設計修改') return showDesign;
        if (!type || type.trim() === '') return showOther;
        return true;
    });

    if (filteredReports.length === 0) {
        list.innerHTML = '<tr><td colspan="12" class="loading-state">目前無符合條件的通報記錄。</td></tr>';
        return;
    }

    const sortedReports = [...filteredReports];
    const sortByEl = document.getElementById('reports-sort-by');
    const sortBy = sortByEl ? sortByEl.value : 'created_at';
    
    const statusPriority = {
        '待處理': 1,
        '維修中': 2,
        '已完成': 3
    };

    sortedReports.sort((a, b) => {
        // Primary: 待處理優先
        const pA = statusPriority[a.status] || 99;
        const pB = statusPriority[b.status] || 99;
        if (pA !== pB) {
            return pA - pB;
        }
        
        // Secondary: 車號 / 問題描述 / 建立時間
        if (sortBy === 'car_number') {
            const carA = (a.car_number || '').trim();
            const carB = (b.car_number || '').trim();
            return carA.localeCompare(carB, 'zh-TW');
        } else if (sortBy === 'description') {
            const descA = (a.description || '').trim();
            const descB = (b.description || '').trim();
            return descA.localeCompare(descB, 'zh-TW');
        } else {
            // Newest first
            return new Date(b.created_at) - new Date(a.created_at);
        }
    });

    sortedReports.forEach((report, index) => {
        const row = document.createElement('tr');
        row.onclick = () => viewDetail(report.id);
        
        const statusMap = {
            '待處理': 'pending',
            '維修中': 'progress',
            '已完成': 'done'
        };
        const statusClass = statusMap[report.status] || 'pending';
        const createdTimeStr = new Date(report.created_at).toLocaleString('zh-TW', { 
            month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false 
        });
        const completedTimeStr = report.completed_at ? new Date(report.completed_at).toLocaleString('zh-TW', { 
            month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false 
        }) : '-';

        const solType = report.solution_type || '-';
        const solTypeClass = report.solution_type === '更換' ? 'sol-replace' : report.solution_type === '維修' ? 'sol-repair' : '';

        row.innerHTML = `
            <td class="row-index">${index + 1}</td>
            <td><span class="status-label ${statusClass}">${report.status}</span></td>
            <td class="cell-car">${report.car_number}</td>
            <td class="cell-desc">${report.description}</td>
            <td class="cell-sol">${report.solution || '-'}</td>
            <td class="cell-reply">${report.reply || report.solution || '-'}</td>
            <td>${report.component || '-'}</td>
            <td><span class="sol-type-label ${solTypeClass}">${solType}</span></td>
            <td class="cell-mileage">${report.mileage || '-'}</td>
            <td>${report.handler_name || '-'}</td>
            <td class="cell-time">${createdTimeStr}</td>
            <td class="cell-time">${completedTimeStr}</td>
            <td>
                <div class="table-actions">
                    <button onclick="event.stopPropagation(); viewDetail('${report.id}')">詳情</button>
                    ${report.status !== '已完成' ? `<button class="btn-primary" onclick="event.stopPropagation(); markDone('${report.id}')">完成</button>` : ''}
                    <button class="btn-danger" onclick="event.stopPropagation(); deleteReport('${report.id}')">刪除</button>
                </div>
            </td>
        `;
        list.appendChild(row);
    });
}

function formatDateTimeLocal(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    const tzoffset = date.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(date.getTime() - tzoffset)).toISOString().slice(0, 16);
    return localISOTime;
}

function viewDetail(id) {
    currentReportId = id;
    const report = allReports.find(r => r.id === id);
    if (!report) return;

    const modal = document.getElementById('modal');
    const body = document.getElementById('modal-body');
    const solutionDisplay = document.getElementById('solution-display');
    const solutionInput = document.getElementById('solution-input');
    
    // Set solution & mileage & reply
    solutionDisplay.innerText = report.solution || "暫無處理紀錄";
    solutionInput.value = report.solution || "";
    document.getElementById('mileage-input').value = report.mileage || "";
    document.getElementById('reply-input').value = report.reply || report.solution || "";

    let mediaHtml = '';
    if (report.media_urls && report.media_urls.length > 0) {
        mediaHtml = `
            <div class="media-container">
                <label>相關相片/影片 (${report.media_urls.length})</label>
                <div class="media-grid">
        `;
        report.media_urls.forEach(url => {
            if (url.toLowerCase().endsWith('.mp4')) {
                mediaHtml += `<video class="media-item" src="${url}" controls></video>`;
            } else {
                mediaHtml += `<img class="media-item" src="${url}" onclick="window.open('${url}')">`;
            }
        });
        mediaHtml += '</div></div>';
    }

    body.innerHTML = `
        <div class="modal-body-content">
            <div class="detail-header">
                <h2 style="margin-bottom:1rem; color:var(--primary);">編輯通報單 #${report.id.substring(0,8)}</h2>
                <div style="margin-bottom:1.5rem; display:flex; gap:.5rem; align-items:center;">
                    <span class="status-label ${report.status === '待處理' ? 'pending' : report.status === '維修中' ? 'progress' : 'done'}">${report.status}</span>
                </div>
            </div>
            
            <div class="detail-row" style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                <div style="flex: 1;">
                    <label>車號</label>
                    <input type="text" id="edit-car-number" value="${report.car_number || ''}">
                </div>
                <div style="flex: 1;">
                    <label>類型</label>
                    <select id="edit-solution-type">
                        <option value="" ${!report.solution_type ? 'selected' : ''}>未選擇</option>
                        <option value="維修" ${report.solution_type === '維修' ? 'selected' : ''}>維修</option>
                        <option value="更換" ${report.solution_type === '更換' ? 'selected' : ''}>更換</option>
                        <option value="設計修改" ${report.solution_type === '設計修改' ? 'selected' : ''}>設計修改</option>
                    </select>
                </div>
            </div>
            
            <div class="detail-row" style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                <div style="flex: 1;">
                    <label>處理人員</label>
                    <input type="text" id="edit-handler-name" value="${report.handler_name || ''}">
                </div>
                <div style="flex: 1;">
                    <label>通報時間</label>
                    <input type="datetime-local" id="edit-created-at" value="${formatDateTimeLocal(report.created_at)}">
                </div>
            </div>

            <div class="detail-row" style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                <div style="flex: 1;">
                    <label>完成時間</label>
                    <input type="datetime-local" id="edit-completed-at" value="${formatDateTimeLocal(report.completed_at)}">
                </div>
                <div style="flex: 1;">
                    <label>部件</label>
                    <select id="edit-component">
                        <option value="" ${!report.component ? 'selected' : ''}>未選擇</option>
                        <option value="TMS" ${report.component === 'TMS' ? 'selected' : ''}>TMS</option>
                        <option value="動力" ${report.component === '動力' ? 'selected' : ''}>動力</option>
                        <option value="BMS" ${report.component === 'BMS' ? 'selected' : ''}>BMS</option>
                        <option value="冷氣" ${report.component === '冷氣' ? 'selected' : ''}>冷氣</option>
                        <option value="電子影像" ${report.component === '電子影像' ? 'selected' : ''}>電子影像</option>
                        <option value="方向燈座" ${report.component === '方向燈座' ? 'selected' : ''}>方向燈座</option>
                        <option value="車門" ${report.component === '車門' ? 'selected' : ''}>車門</option>
                        <option value="車裝" ${report.component === '車裝' ? 'selected' : ''}>車裝</option>
                        <option value="燈光" ${report.component === '燈光' ? 'selected' : ''}>燈光</option>
                        <option value="底盤件" ${report.component === '底盤件' ? 'selected' : ''}>底盤件</option>
                        <option value="儀錶" ${report.component === '儀錶' ? 'selected' : ''}>儀錶</option>
                        <option value="其他" ${report.component === '其他' ? 'selected' : ''}>其他</option>
                    </select>
                </div>
            </div>

            <div class="detail-row" style="margin-bottom: 1rem;">
                <label>問題描述</label>
                <textarea id="edit-description" rows="3">${report.description || ''}</textarea>
            </div>

            ${mediaHtml}

            <div class="modal-actions">
                ${report.status === '待處理' ? `<button class="btn-primary" onclick="updateStatus('${id}', '維修中')">進入維修</button>` : ''}
                ${report.status !== '已完成' ? `<button class="btn-primary" onclick="markDone('${id}')">完成維修並通知</button>` : ''}
                <button class="btn-danger" onclick="deleteReport('${id}'); closeModal();">刪除</button>
                <button class="btn-secondary" onclick="closeModal()">關閉</button>
            </div>
        </div>
    `;
    modal.classList.remove('hidden');
}

async function saveSolution() {
    if (!currentReportId) return;
    
    const car_number = document.getElementById('edit-car-number').value.trim();
    const description = document.getElementById('edit-description').value.trim();
    const solution_type = document.getElementById('edit-solution-type').value;
    const component = document.getElementById('edit-component').value;
    const handler_name = document.getElementById('edit-handler-name').value.trim();
    const solution = document.getElementById('solution-input').value.trim();
    const reply = document.getElementById('reply-input').value.trim();
    const mileage = document.getElementById('mileage-input').value.trim();
    
    const created_at_val = document.getElementById('edit-created-at').value;
    const completed_at_val = document.getElementById('edit-completed-at').value;
    
    const created_at = created_at_val ? new Date(created_at_val).toISOString() : null;
    const completed_at = completed_at_val ? new Date(completed_at_val).toISOString() : null;
    
    if (!car_number) {
        showToast("車號不能為空", "error");
        return;
    }
    if (!description) {
        showToast("問題描述不能為空", "error");
        return;
    }

    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${currentReportId}`, {
            method: 'PATCH',
            headers: { 
                'token': token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                car_number,
                description,
                solution_type,
                component,
                handler_name,
                solution,
                reply: reply || solution,
                mileage,
                created_at,
                completed_at
            })
        });
        if (response.ok) {
            showToast("修改已儲存");
            const now = new Date().toISOString();
            
            let updatedCompletedAt = completed_at;
            if (solution && !updatedCompletedAt) {
                const report = allReports.find(r => r.id === currentReportId);
                updatedCompletedAt = (report && report.completed_at) ? report.completed_at : now;
            }
            
            allReports = allReports.map(r => r.id === currentReportId ? { 
                ...r, 
                car_number, 
                description, 
                solution_type, 
                component,
                handler_name, 
                solution, 
                reply: reply || solution,
                mileage, 
                created_at: created_at || r.created_at,
                completed_at: updatedCompletedAt,
                status: solution ? '已完成' : r.status
            } : r);
            
            renderReports(); // Refresh table
            updateStats();   // Refresh stats in case status changed
            closeModal();    // Close the modal
        } else {
            showToast("儲存失敗", "error");
        }
    } catch (error) {
        showToast("網路錯誤", "error");
    }
}

async function deleteReport(id) {
    if (!confirm("確定要永久刪除這筆通報嗎？此操作不可還原。")) return;
    
    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${id}`, {
            method: 'DELETE',
            headers: { 'token': token }
        });
        if (response.ok) {
            showToast("通報已刪除");
            allReports = allReports.filter(r => r.id !== id);
            renderReports();
            updateStats();
        }
    } catch (error) {
        showToast("刪除失敗", "error");
    }
}

function updateStats() {
    const countPendingEl = document.getElementById('count-pending');
    if (countPendingEl) countPendingEl.innerText = allReports.filter(r => r.status === '待處理').length;
    const countInProgressEl = document.getElementById('count-in-progress');
    if (countInProgressEl) countInProgressEl.innerText = allReports.filter(r => r.status === '維修中').length;
    const countDoneEl = document.getElementById('count-done');
    if (countDoneEl) countDoneEl.innerText = allReports.filter(r => r.status === '已完成').length;
    
    // 同步更新統計分頁數據
    if (monitoredBuses && monitoredBuses.length > 0) {
        populateStatsSolutionTypes();
        calculateStats();
    }

    // 同步更新導出報表分頁數據
    if (document.getElementById('tab-export').classList.contains('active')) {
        renderExportTable();
    }
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

async function updateStatus(id, status, mileage = null) {
    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${id}`, {
            method: 'PATCH',
            headers: { 
                'token': token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status, mileage })
        });
        if (response.ok) {
            // Need to fetch again or update locally with completion time
            // For simplicity, let's just refresh or update locally if we know what changed
            if (status === '已完成') {
                const now = new Date().toISOString();
                allReports = allReports.map(r => r.id === id ? { ...r, status, mileage: mileage || r.mileage, completed_at: now } : r);
            } else {
                allReports = allReports.map(r => r.id === id ? { ...r, status } : r);
            }
            renderReports();
            updateStats();
            if (!document.getElementById('modal').classList.contains('hidden')) {
                viewDetail(id);
            }
        }
    } catch (error) {
        showToast("更新狀態失敗", "error");
    }
}

async function markDone(id) {
    const mileage = prompt("請輸入維修完成時的里程 (選填):", "");
    if (mileage === null) return; // Cancelled
    
    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${id}/notify`, {
            method: 'POST',
            headers: { 'token': token }
        });
        
        if (response.ok) {
            await updateStatus(id, '已完成', mileage);
            showToast("已更新狀態、里程並發送通知！");
            closeModal();
        } else {
            showToast("發送通知失敗", "error");
        }
    } catch (error) {
        showToast("操作過程發生錯誤", "error");
    }
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

// --- GPS Tab Logic ---
let gpsChart = null;

function switchTab(tabId) {
    // Update active class on buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('onclick').includes(tabId)) {
            btn.classList.add('active');
        }
    });

    // Show/Hide tabs
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
        content.classList.remove('active');
    });
    
    document.getElementById(tabId).classList.remove('hidden');
    document.getElementById(tabId).classList.add('active');

    if (tabId === 'tab-gps') {
        const datePicker = document.getElementById('gps-date-picker');
        if (!datePicker.value) {
            // Set default date to today
            const today = new Date();
            const yyyy = today.getFullYear();
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const dd = String(today.getDate()).padStart(2, '0');
            datePicker.value = `${yyyy}-${mm}-${dd}`;
        }
        loadGPSLog();
    } else if (tabId === 'tab-plans') {
        loadPlates();
        loadPlans();
    } else if (tabId === 'tab-stats') {
        loadStatsData();
    } else if (tabId === 'tab-export') {
        loadExportTab();
    } else if (tabId === 'tab-quality') {
        loadQualityStats();
    }
}

async function loadGPSLog() {
    const tokenInput = document.getElementById('admin-token');
    const token = tokenInput.value.trim();
    const date = document.getElementById('gps-date-picker').value;

    if (!token) return;

    try {
        const response = await fetch(`/admin/weekly_gps_log?date=${date}`, {
            headers: { 'token': token }
        });

        if (!response.ok) throw new Error("API Error");

        const logs = await response.json();
        renderGPSChart(logs, date);
    } catch (error) {
        console.error("Failed to load GPS logs", error);
        showToast("無法載入 GPS 紀錄", "error");
    }
}

function renderGPSChart(logs, dateStr) {
    const container = document.getElementById('gps-timeline-chart');
    container.innerHTML = '';

    if (!logs || logs.length === 0) {
        container.innerHTML = `<div class="loading-state">此日期無任何車輛 GPS 紀錄。</div>`;
        return;
    }

    // Process data for ApexCharts rangeBar
    // We group by plate_number
    const seriesData = [];
    
    logs.forEach(log => {
        const start = new Date(log.recorded_at).getTime();
        // Since we collect every 5 mins, we draw a 5-min block for visualization
        const end = start + 5 * 60 * 1000; 
        
        seriesData.push({
            x: `${log.plate_number}\n(${log.route_name})`,
            y: [start, end]
        });
    });

    // Set chart min/max to 07:00 - 23:00 of the selected date
    const minTime = new Date(`${dateStr}T07:00:00+08:00`).getTime();
    const maxTime = new Date(`${dateStr}T23:00:00+08:00`).getTime();

    const options = {
        series: [
            {
                name: 'GPS 紀錄',
                data: seriesData
            }
        ],
        chart: {
            height: Math.max(500, Object.keys(logs).length * 10), // Adjust height based on number of records roughly
            type: 'rangeBar',
            background: 'transparent',
            toolbar: { show: false }
        },
        plotOptions: {
            bar: {
                horizontal: true,
                barHeight: '50%',
                borderRadius: 4
            }
        },
        colors: ['#0ea5e9'],
        xaxis: {
            type: 'datetime',
            min: minTime,
            max: maxTime,
            labels: {
                datetimeUTC: false,
                format: 'HH:mm',
                style: { colors: '#94a3b8' }
            },
            axisBorder: { show: false },
            axisTicks: { show: false }
        },
        yaxis: {
            labels: {
                style: { colors: '#f8fafc', fontSize: '12px', fontFamily: 'Outfit' }
            }
        },
        grid: {
            borderColor: '#334155',
            strokeDashArray: 4,
            xaxis: { lines: { show: true } },
            yaxis: { lines: { show: false } }
        },
        theme: { mode: 'dark' },
        tooltip: {
            x: {
                format: 'HH:mm'
            }
        }
    };

    if (gpsChart) {
        gpsChart.destroy();
    }

    gpsChart = new ApexCharts(document.querySelector("#gps-timeline-chart"), options);
    gpsChart.render();
}

// --- 導出報表功能 ---
function openExportModal() {
    const modal = document.getElementById('export-modal');
    modal.classList.remove('hidden');
    
    const typeSelect = document.getElementById('export-type');
    const startInput = document.getElementById('export-start');
    const endInput = document.getElementById('export-end');

    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];
    
    // 監聽類型切換，自動調整日期範圍
    typeSelect.onchange = () => {
        const days = typeSelect.value === 'replacement' ? 7 : 30;
        const startDate = new Date();
        startDate.setDate(today.getDate() - days);
        startInput.value = startDate.toISOString().split('T')[0];
        endInput.value = todayStr;
    };

    // 初始預設值
    typeSelect.onchange();
}

function closeExportModal() {
    document.getElementById('export-modal').classList.add('hidden');
}

async function doExport() {
    const type = document.getElementById('export-type').value;
    const start = document.getElementById('export-start').value;
    const end = document.getElementById('export-end').value;
    const token = document.getElementById('admin-token').value;

    if (!start || !end) {
        showToast("請選擇日期範圍", "error");
        return;
    }

    // Filter reports from allReports matching dates and status '已完成'
    const targetReports = allReports.filter(r => {
        if (r.status !== '已完成') return false;
        if (!r.completed_at) return false;
        const completedDate = r.completed_at.slice(0, 10);
        if (completedDate < start || completedDate > end) return false;
        if (type === 'replacement') {
            return r.solution_type === '更換';
        }
        return true;
    });

    if (targetReports.length === 0) {
        showToast("該日期範圍內無已完成紀錄", "error");
        return;
    }

    showToast("報表產生中，請稍候...", "success");

    // Group by vendor and month
    const groups = {};
    targetReports.forEach(r => {
        let vendor = '未知客運';
        const car = (r.car_number || '').trim();
        if (monitoredBuses && monitoredBuses.length > 0) {
            const found = monitoredBuses.find(b => (b.plate_number || '').trim() === car);
            if (found) {
                vendor = found.vendor_name || '未知客運';
            }
        }
        r.vendor_name = vendor;
        const month = r.completed_at ? r.completed_at.slice(0, 7) : '無日期';
        const key = `${vendor}_${month}`;
        if (!groups[key]) {
            groups[key] = { vendor, month, ids: [] };
        }
        groups[key].ids.push(r.id);
    });

    let successCount = 0;
    for (const group of Object.values(groups)) {
        try {
            const response = await fetch('/admin/export/custom', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'token': token
                },
                body: JSON.stringify({
                    ids: group.ids,
                    format: 'pdf',
                    export_type: type,
                    content_field: 'solution'
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || `匯出 ${group.vendor} PDF 失敗`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${group.vendor}_${group.month.replace('-', '年')}月.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            successCount++;
        } catch (e) {
            console.error("Export Group Error:", e);
            showToast(e.message, "error");
        }
    }

    if (successCount > 0) {
        showToast(`成功匯出 ${successCount} 個 PDF 檔案！`, "success");
        closeExportModal();
    }
}

// --- Operating Plans Logic ---

async function loadPlates() {
    const token = document.getElementById('admin-token').value;
    const select = document.getElementById('plan-plate-filter');
    const currentVal = select.value;

    try {
        const response = await fetch('/admin/bus_plates', { headers: { 'token': token } });
        const { plates } = await response.json();
        
        select.innerHTML = '<option value="">選擇車號...</option>';
        plates.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.innerText = p;
            if (p === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (error) {
        console.error("Failed to load plates", error);
    }
}

async function analyzeSelectedVehicle() {
    const token = document.getElementById('admin-token').value;
    const plate = document.getElementById('plan-plate-filter').value;
    const btn = document.getElementById('btn-analyze-selected');

    if (!plate) {
        showToast("請先選擇車號", "warning");
        return;
    }

    if (!confirm(`確定要分析 ${plate} 的所有紀錄嗎？\n這可能需要幾分鐘時間。`)) return;

    btn.disabled = true;
    btn.innerText = "⏳ 分析中...";
    showToast(`正在開始分析 ${plate}...`, "info");

    try {
        const response = await fetch('/admin/bus_plans/analyze_selected', {
            method: 'POST',
            headers: { 'token': token, 'Content-Type': 'application/json' },
            body: JSON.stringify({ plate_number: plate })
        });
        const result = await response.json();
        showToast(`分析完成！新增 ${result.analyzed_count} 筆紀錄`, "success");
        loadPlans();
    } catch (error) {
        showToast("分析失敗", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "🧠 分析此車紀錄";
    }
}

function renderPlans(plans) {
    const container = document.getElementById('plans-container');
    if (!plans || plans.length === 0) {
        container.innerHTML = `<div class="empty-state">尚未分析完成。請點擊「分析此車紀錄」或調整查詢條件。</div>`;
        return;
    }

    let html = `
        <div class="table-container">
            <table class="plans-table">
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>車號</th>
                        <th>方案名稱</th>
                        <th>路線摘要</th>
                        <th>總里程</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
    `;

    plans.forEach((plan, index) => {
        const lastGps = (plan.route_details || []).find(r => r.is_last_gps);
        const routesOnly = (plan.route_details || []).filter(r => !r.is_last_gps);

        html += `
            <tr>
                <td>${plan.date}</td>
                <td><span class="badge-plate">${plan.plate_number}</span></td>
                <td>${plan.plan_name}</td>
                <td class="text-truncate" title="${plan.route_summary}">${plan.route_summary || '-'}</td>
                <td><strong>${plan.total_mileage}</strong> km</td>
                <td>
                    <button class="btn-small" onclick="toggleDetails(${index})">詳情</button>
                </td>
            </tr>
            <tr id="details-${index}" class="detail-row hidden">
                <td colspan="6">
                    <div class="plan-details-content">
                        <div class="details-grid">
                            <div class="details-section">
                                <h4>🚌 路線行程</h4>
                                <div class="timeline">
                                    ${routesOnly.map(r => `
                                        <div class="timeline-item">
                                            <span class="time">${r.start_time} - ${r.end_time}</span>
                                            <span class="desc">${r.route}</span>
                                        </div>
                                    `).join('') || '無資料'}
                                </div>
                            </div>
                            <div class="details-section">
                                <h4>⏸️ 中退紀錄</h4>
                                <div class="timeline timeline-break">
                                    ${(plan.break_details || []).map(b => {
                                        const locText = b.lat && b.lon ? `<a href="https://www.google.com/maps?q=${b.lat},${b.lon}" target="_blank" style="color: #38bdf8; text-decoration: underline;">場站/路邊 (${b.lat.toFixed(4)}, ${b.lon.toFixed(4)})</a>` : b.location;
                                        return `
                                            <div class="timeline-item">
                                                <span class="time">${b.start_time} - ${b.end_time}</span>
                                                <span class="desc">${locText}</span>
                                            </div>
                                        `;
                                    }).join('') || '無資料'}
                                </div>
                            </div>
                        </div>
                        ${lastGps ? `
                            <div class="plan-last-gps" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed #334155;">
                                <label style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">📍 GPS 當日紀錄最後位置</label>
                                <p style="margin: 0.25rem 0 0 0; font-size: 0.95rem; color: #f8fafc; font-family: monospace;">
                                    <a href="https://www.google.com/maps?q=${lastGps.lat},${lastGps.lon}" target="_blank" style="color: #38bdf8; text-decoration: underline;">
                                        ${lastGps.lat.toFixed(6)}, ${lastGps.lon.toFixed(6)}
                                    </a>
                                    <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 0.5rem;">(${lastGps.time})</span>
                                </p>
                            </div>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    });

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

function toggleDetails(index) {
    const row = document.getElementById(`details-${index}`);
    row.classList.toggle('hidden');
}

async function loadPlans() {
    const token = document.getElementById('admin-token').value;
    const plate = document.getElementById('plan-plate-filter').value;
    const date = document.getElementById('plan-date-filter').value;
    const container = document.getElementById('plans-container');

    container.innerHTML = `<div class="loading-state">正在載入方案資料...</div>`;

    let url = '/admin/bus_plans?';
    if (plate) url += `plate_number=${plate}&`;
    if (date) url += `date=${date}&`;

    try {
        const response = await fetch(url, { headers: { 'token': token } });
        const plans = await response.json();
        renderPlans(plans);
    } catch (error) {
        showToast("載入方案失敗", "error");
    }
}

function renderPlans(plans) {
    const container = document.getElementById('plans-container');
    container.innerHTML = '';

    if (!plans || plans.length === 0) {
        container.innerHTML = `<div class="loading-state">尚無分析完成的方案。請先執行「批次分析」或調整查詢條件。</div>`;
        return;
    }

    plans.forEach(plan => {
        const card = document.createElement('div');
        card.className = 'plan-card';
        
        const breakHtml = (plan.break_details || []).map(b => {
            const locText = b.lat && b.lon ? `<a href="https://www.google.com/maps?q=${b.lat},${b.lon}" target="_blank" style="color: #38bdf8; text-decoration: underline;">場站/路邊 (${b.lat.toFixed(4)}, ${b.lon.toFixed(4)})</a>` : b.location;
            return `
                <div class="break-item">
                    <span>⏱️ ${b.start_time} - ${b.end_time}</span>
                    <span>📍 ${locText}</span>
                </div>
            `;
        }).join('') || '<p>無中退紀錄</p>';

        const routesOnly = (plan.route_details || []).filter(r => !r.is_last_gps);
        const routeHtml = routesOnly.map(r => `
            <li>${r.start_time}-${r.end_time}: <strong>${r.route}</strong></li>
        `).join('') || '<li>無詳細路線資料</li>';

        const lastGps = (plan.route_details || []).find(r => r.is_last_gps);
        const lastGpsHtml = lastGps ? `
            <div class="plan-last-gps" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed #334155; display: flex; flex-direction: column; gap: 0.25rem;">
                <label style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">📍 GPS 當日紀錄最後位置</label>
                <p style="margin: 0; font-size: 0.95rem; color: #f8fafc; font-family: monospace;">
                    <a href="https://www.google.com/maps?q=${lastGps.lat},${lastGps.lon}" target="_blank" style="color: #38bdf8; text-decoration: underline;">
                        ${lastGps.lat.toFixed(6)}, ${lastGps.lon.toFixed(6)}
                    </a>
                    <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 0.5rem;">(${lastGps.time})</span>
                </p>
            </div>
        ` : '';

        card.innerHTML = `
            <div class="plan-card-header">
                <h3>${plan.plate_number} <span class="badge">${plan.plan_name}</span></h3>
                <span class="plan-date">${plan.date}</span>
            </div>
            <div class="plan-card-body">
                <div class="plan-summary">
                    <label>當日路線總覽</label>
                    <p>${plan.route_summary || '無'}</p>
                </div>
                <div class="plan-mileage">
                    <label>當日估算總里程</label>
                    <div class="mileage-value">${plan.total_mileage || 0} <small>KM</small></div>
                </div>
                <div class="plan-details-grid">
                    <div class="plan-routes">
                        <label>🕒 時段與路線</label>
                        <ul>${routeHtml}</ul>
                    </div>
                    <div class="plan-breaks">
                        <label>☕ 中退紀錄</label>
                        ${breakHtml}
                    </div>
                </div>
                ${lastGpsHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

async function syncSchedules() {
    const token = document.getElementById('admin-token').value;
    showToast("正在從 TDX 同步台南與高雄時刻表...");
    try {
        console.log("Starting sync for Kaohsiung...");
        const resK = await fetch('/admin/bus_plans/sync_schedules?city=Kaohsiung', {
            method: 'POST', headers: { 'token': token }
        }).then(async r => {
            if (!r.ok) throw new Error(`Kaohsiung sync failed: ${r.status}`);
            return r.json();
        });
        
        console.log("Starting sync for Tainan...");
        const resT = await fetch('/admin/bus_plans/sync_schedules?city=Tainan', {
            method: 'POST', headers: { 'token': token }
        }).then(async r => {
            if (!r.ok) throw new Error(`Tainan sync failed: ${r.status}`);
            return r.json();
        });
        
        showToast(`同步完成！高雄: ${resK.count} 筆, 台南: ${resT.count} 筆`);
        console.log("Sync results:", { resK, resT });
    } catch (error) {
        console.error("Sync Error:", error);
        showToast(`同步失敗: ${error.message}`, "error");
    }
}

async function analyzeAllLogs() {
    const token = document.getElementById('admin-token').value;
    if (!confirm("這將會分析所有現存的 GPS 紀錄，可能需要數分鐘時間且會消耗 AI 額度。確定開始？")) return;

    showToast("AI 分析中，請勿關閉視窗...", "success");
    try {
        console.log("Starting batch analysis...");
        const response = await fetch('/admin/bus_plans/analyze_all', {
            method: 'POST',
            headers: { 'token': token }
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Analysis failed: ${response.status}`);
        }
        
        const res = await response.json();
        console.log("Analysis results:", res);
        showToast(res.message || `分析完成！共產生 ${res.analyzed_count} 筆方案`);
        loadPlans();
    } catch (error) {
        console.error("Analysis Error:", error);
        showToast(`分析過程發生錯誤: ${error.message}`, "error");
    }
}

// ==========================================================================
// 設計修改統計分頁邏輯 (Tab: Statistics)
// ==========================================================================
let monitoredBuses = [];
let statsRadialChart = null;
let statsFilteredBuses = [];
let uncheckedPlates = new Set();
let selectedExportIds = new Set();
let exportInitialized = false;

function loadUncheckedPlates() {
    try {
        const saved = localStorage.getItem('unchecked_plates');
        if (saved) {
            uncheckedPlates = new Set(JSON.parse(saved));
        } else {
            uncheckedPlates = new Set();
        }
    } catch (e) {
        uncheckedPlates = new Set();
    }
}

async function loadStatsData() {
    const token = document.getElementById('admin-token').value;
    if (!token) return;

    try {
        const response = await fetch('/admin/monitored_buses', {
            headers: { 'token': token }
        });

        if (!response.ok) throw new Error("無法取得監控車輛列表");

        monitoredBuses = await response.json();
        
        // 載入未勾選的車牌歷史狀態
        loadUncheckedPlates();
        
        // 渲染客運商核取方塊
        populateVendorCheckboxes();
        
        // 渲染修改類型下拉選單
        populateStatsSolutionTypes();
        
        // 計算與渲染統計結果
        calculateStats();
    } catch (error) {
        console.error("Failed to load monitored buses stats data:", error);
        showToast("載入車輛統計數據失敗", "error");
    }
}

function populateVendorCheckboxes() {
    const container = document.getElementById('vendor-checkboxes');
    if (!container) return;

    const vendors = [...new Set(monitoredBuses.map(b => b.vendor_name || '未知客運'))].sort();
    
    // 從 localStorage 讀取已存勾選狀態
    let savedCheckedVendors = null;
    try {
        const saved = localStorage.getItem('selected_vendors');
        if (saved) savedCheckedVendors = new Set(JSON.parse(saved));
    } catch (e) {
        console.error("Error reading selected_vendors from localStorage:", e);
    }
    
    container.innerHTML = '';
    
    vendors.forEach(vendor => {
        const div = document.createElement('div');
        // 預設為全選
        const isChecked = savedCheckedVendors === null || savedCheckedVendors.has(vendor);
        div.innerHTML = `
            <label class="checkbox-label" title="${vendor}">
                <input type="checkbox" value="${vendor}" ${isChecked ? 'checked' : ''} onchange="onVendorCheckboxChange()">
                ${vendor}
            </label>
        `;
        container.appendChild(div);
    });
}

function onVendorCheckboxChange() {
    const selectedVendors = [];
    document.querySelectorAll('#vendor-checkboxes input[type="checkbox"]:checked').forEach(cb => {
        selectedVendors.push(cb.value);
    });
    localStorage.setItem('selected_vendors', JSON.stringify(selectedVendors));
    calculateStats();
}

function populateStatsSolutionTypes() {
    const select = document.getElementById('stats-solution-type');
    if (!select) return;

    const currentVal = select.value || '設計修改';
    
    // 從現有通報單撈取所有的 solution_type 類型
    let types = [...new Set(allReports.map(r => r.solution_type).filter(Boolean))];
    
    // 預設一定要有這三種基本類型
    const defaults = ['設計修改', '維修', '更換'];
    defaults.forEach(d => {
        if (!types.includes(d)) {
            types.push(d);
        }
    });
    
    types = types.sort();
    
    select.innerHTML = '';
    types.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t;
        opt.innerText = t;
        if (t === currentVal) opt.selected = true;
        select.appendChild(opt);
    });
    
    onStatsTypeChange();
}

function onStatsTypeChange() {
    const typeSelect = document.getElementById('stats-solution-type');
    const solSelect = document.getElementById('stats-solution');
    if (!typeSelect || !solSelect) return;

    const selectedType = typeSelect.value;
    const prevSol = solSelect.value;
    
    // 篩選出已完成、符合該類型且有填處理方案的通報
    const matchingReports = allReports.filter(r => 
        r.status === '已完成' && 
        r.solution_type === selectedType && 
        r.solution
    );
    
    // 取得不重複的處理方案 (unique solutions matching type)
    const uniqueSolutions = [...new Set(matchingReports.map(r => r.solution))].sort();
    
    solSelect.innerHTML = '<option value="">選擇處理方案...</option>';
    uniqueSolutions.forEach(sol => {
        const opt = document.createElement('option');
        opt.value = sol;
        opt.innerText = sol;
        if (sol === prevSol) opt.selected = true;
        solSelect.appendChild(opt);
    });
    
    calculateStats();
}

function calculateStats() {
    const typeSelect = document.getElementById('stats-solution-type');
    const solSelect = document.getElementById('stats-solution');
    
    const totalBusesEl = document.getElementById('stats-total-buses');
    const completedBusesEl = document.getElementById('stats-completed-buses');
    const ratioEl = document.getElementById('stats-ratio');
    
    if (!typeSelect || !solSelect || !totalBusesEl || !completedBusesEl || !ratioEl) return;

    const selectedType = typeSelect.value;
    const selectedSol = solSelect.value;
    
    // 獲取勾選的客運商
    const selectedVendors = [];
    document.querySelectorAll('#vendor-checkboxes input[type="checkbox"]:checked').forEach(cb => {
        selectedVendors.push(cb.value);
    });
    
    // 如果未選擇任何客運商，或是未選擇處理方案，則呈現 0
    if (selectedVendors.length === 0 || !selectedSol) {
        totalBusesEl.innerText = '0';
        completedBusesEl.innerText = '0';
        ratioEl.innerText = '0%';
        statsFilteredBuses = [];
        renderStatsBusesTable();
        updateRadialChart(0);
        return;
    }
    
    // 篩選出屬於已勾選客運商的車輛
    const targetBuses = monitoredBuses.filter(b => selectedVendors.includes(b.vendor_name || '未知客運'));
    
    // 篩選出該類型、該方案且已完成的通報記錄
    const completedReports = allReports.filter(r => 
        r.status === '已完成' && 
        r.solution_type === selectedType && 
        r.solution === selectedSol
    );
    
    // 建立車牌對應通報記錄的 Map
    const completedMap = new Map();
    completedReports.forEach(r => {
        const car = (r.car_number || '').trim();
        if (car) {
            // 如有多筆相同車牌的完成記錄，取最新的一筆
            if (!completedMap.has(car) || new Date(r.completed_at) > new Date(completedMap.get(car).completed_at)) {
                completedMap.set(car, r);
            }
        }
    });
    
    let totalCount = 0;
    let completedCount = 0;
    statsFilteredBuses = targetBuses.map(bus => {
        const plate = (bus.plate_number || '').trim();
        const report = completedMap.get(plate);
        const isCompleted = !!report;
        
        const isChecked = !uncheckedPlates.has(plate);
        if (isChecked) {
            totalCount++;
            if (isCompleted) completedCount++;
        }
        
        return {
            plate_number: bus.plate_number,
            vendor_name: bus.vendor_name || '未知客運',
            is_completed: isCompleted,
            is_checked: isChecked,
            completed_at: report ? report.completed_at : null,
            handler_name: report ? report.handler_name : null
        };
    });
    
    statsFilteredBuses.sort((a, b) => (a.plate_number || '').localeCompare(b.plate_number || '', 'zh-TW'));
    
    const ratio = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
    
    totalBusesEl.innerText = totalCount;
    completedBusesEl.innerText = completedCount;
    ratioEl.innerText = `${ratio}%`;
    
    renderStatsBusesTable();
    updateRadialChart(ratio);
}

function renderStatsBusesTable() {
    const listBody = document.getElementById('stats-bus-list');
    const searchInput = document.getElementById('stats-bus-search');
    if (!listBody || !searchInput) return;

    const searchQuery = searchInput.value.toLowerCase().trim();
    
    const filterEl = document.querySelector('input[name="stats-filter"]:checked');
    const filterVal = filterEl ? filterEl.value : 'all';
    
    listBody.innerHTML = '';
    
    let displayBuses = statsFilteredBuses;
    
    // 車號關鍵字搜尋
    if (searchQuery) {
        displayBuses = displayBuses.filter(b => b.plate_number.toLowerCase().includes(searchQuery));
    }
    
    // 狀態篩選
    if (filterVal === 'completed') {
        displayBuses = displayBuses.filter(b => b.is_completed);
    } else if (filterVal === 'pending') {
        displayBuses = displayBuses.filter(b => !b.is_completed);
    }
    
    if (displayBuses.length === 0) {
        listBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">查無符合的車輛資料</td></tr>';
        return;
    }
    
    displayBuses.forEach(b => {
        const row = document.createElement('tr');
        
        const statusBadge = b.is_completed 
            ? '<span class="badge-status completed">已完成</span>' 
            : '<span class="badge-status pending">未完成</span>';
            
        const timeStr = b.completed_at 
            ? new Date(b.completed_at).toLocaleString('zh-TW', { 
                month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false 
              })
            : '-';
            
        row.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="bus-checkbox" data-plate="${b.plate_number}" ${b.is_checked ? 'checked' : ''} onchange="toggleBusCheckbox(this)">
            </td>
            <td style="font-weight: 600; color: var(--primary);">${b.plate_number}</td>
            <td>${b.vendor_name}</td>
            <td>${statusBadge}</td>
            <td>${timeStr}</td>
            <td>${b.handler_name || '-'}</td>
        `;
        listBody.appendChild(row);
    });

    // 同步 Master Checkbox 狀態
    const masterCheckbox = document.getElementById('stats-select-all-buses');
    if (masterCheckbox) {
        const allVisibleChecked = displayBuses.length > 0 && displayBuses.every(b => b.is_checked);
        const someVisibleChecked = displayBuses.some(b => b.is_checked);
        masterCheckbox.checked = allVisibleChecked;
        masterCheckbox.indeterminate = someVisibleChecked && !allVisibleChecked;
    }
}

function toggleBusCheckbox(el) {
    const plate = el.getAttribute('data-plate');
    if (el.checked) {
        uncheckedPlates.delete(plate);
    } else {
        uncheckedPlates.add(plate);
    }
    localStorage.setItem('unchecked_plates', JSON.stringify(Array.from(uncheckedPlates)));
    calculateStats();
}

function toggleAllStatsBuses(masterEl) {
    const checked = masterEl.checked;
    
    const searchInput = document.getElementById('stats-bus-search');
    const searchQuery = searchInput ? searchInput.value.toLowerCase().trim() : '';
    const filterEl = document.querySelector('input[name="stats-filter"]:checked');
    const filterVal = filterEl ? filterEl.value : 'all';
    
    let displayBuses = statsFilteredBuses;
    if (searchQuery) {
        displayBuses = displayBuses.filter(b => b.plate_number.toLowerCase().includes(searchQuery));
    }
    if (filterVal === 'completed') {
        displayBuses = displayBuses.filter(b => b.is_completed);
    } else if (filterVal === 'pending') {
        displayBuses = displayBuses.filter(b => !b.is_completed);
    }
    
    displayBuses.forEach(b => {
        const plate = b.plate_number;
        if (checked) {
            uncheckedPlates.delete(plate);
        } else {
            uncheckedPlates.add(plate);
        }
    });
    
    localStorage.setItem('unchecked_plates', JSON.stringify(Array.from(uncheckedPlates)));
    calculateStats();
}

function updateRadialChart(ratio) {
    const container = document.querySelector("#stats-radial-chart");
    if (!container) return;

    const options = {
        series: [ratio],
        chart: {
            height: 280,
            type: 'radialBar',
            background: 'transparent'
        },
        plotOptions: {
            radialBar: {
                hollow: {
                    size: '70%',
                },
                dataLabels: {
                    name: {
                        show: true,
                        color: '#94a3b8',
                        fontSize: '14px',
                        fontWeight: 600,
                        offsetY: -10
                    },
                    value: {
                        show: true,
                        color: '#ffffff',
                        fontSize: '30px',
                        fontWeight: 700,
                        offsetY: 5,
                        formatter: function (val) {
                            return val + "%";
                        }
                    }
                },
                track: {
                    background: '#1e293b',
                    strokeWidth: '97%',
                }
            }
        },
        colors: ['#3b82f6'],
        labels: ['已完成修改比例'],
        theme: { mode: 'dark' }
    };
    
    if (statsRadialChart) {
        statsRadialChart.destroy();
    }
    
    container.innerHTML = '';
    statsRadialChart = new ApexCharts(container, options);
    statsRadialChart.render();
}

// ==========================================================================
// 導出報表分頁邏輯 (Tab: Export Reports)
// ==========================================================================
function loadExportTab() {
    const startDateEl = document.getElementById('export-start-date');
    const endDateEl = document.getElementById('export-end-date');
    
    if (startDateEl && !startDateEl.value) {
        const now = new Date();
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
        const yyyy = firstDay.getFullYear();
        const mm = String(firstDay.getMonth() + 1).padStart(2, '0');
        startDateEl.value = `${yyyy}-${mm}-01`;
    }
    if (endDateEl && !endDateEl.value) {
        const now = new Date();
        const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        const yyyy = lastDay.getFullYear();
        const mm = String(lastDay.getMonth() + 1).padStart(2, '0');
        const dd = String(lastDay.getDate()).padStart(2, '0');
        endDateEl.value = `${yyyy}-${mm}-${dd}`;
    }

    if (!exportInitialized) {
        resetExportSelection();
        exportInitialized = true;
    }
    
    renderExportTable();
}

function onExportFilterChange() {
    resetExportSelection();
    renderExportTable();
}

function resetExportSelection() {
    selectedExportIds.clear();
    
    const start = document.getElementById('export-start-date').value;
    const end = document.getElementById('export-end-date').value;
    const showReplace = document.getElementById('export-filter-replace').checked;
    const showRepair = document.getElementById('export-filter-repair').checked;
    const showDesign = document.getElementById('export-filter-design').checked;
    
    allReports.forEach(r => {
        if (r.status !== '已完成') return;
        
        // Date check
        if (r.completed_at) {
            const completedDate = r.completed_at.slice(0, 10);
            if (start && completedDate < start) return;
            if (end && completedDate > end) return;
        } else {
            return;
        }
        
        // Type check
        const type = r.solution_type;
        if (type === '更換' && !showReplace) return;
        if (type === '維修' && !showRepair) return;
        if (type === '設計修改' && !showDesign) return;
        
        selectedExportIds.add(r.id);
    });
}

function renderExportTable() {
    const listBody = document.getElementById('export-table-list');
    const selectedCountEl = document.getElementById('export-selected-count');
    if (!listBody || !selectedCountEl) return;
    
    const start = document.getElementById('export-start-date').value;
    const end = document.getElementById('export-end-date').value;
    const showReplace = document.getElementById('export-filter-replace').checked;
    const showRepair = document.getElementById('export-filter-repair').checked;
    const showDesign = document.getElementById('export-filter-design').checked;
    
    // 篩選出符合日期與勾選類型的已完成通報紀錄
    const displayReports = allReports.filter(r => {
        if (r.status !== '已完成') return false;
        
        if (r.completed_at) {
            const completedDate = r.completed_at.slice(0, 10);
            if (start && completedDate < start) return false;
            if (end && completedDate > end) return false;
        } else {
            return false;
        }
        
        const type = r.solution_type;
        if (type === '更換') return showReplace;
        if (type === '維修') return showRepair;
        if (type === '設計修改') return showDesign;
        
        return false;
    });
    
    // 排序：完成時間由新到舊
    displayReports.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));
    
    listBody.innerHTML = '';
    
    if (displayReports.length === 0) {
        listBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">所選日期區間與類型查無已完成通報紀錄</td></tr>';
        selectedCountEl.innerText = '0';
        return;
    }
    
    let visibleSelectedCount = 0;
    
    displayReports.forEach(r => {
        const isChecked = selectedExportIds.has(r.id);
        if (isChecked) visibleSelectedCount++;
        
        const completedTimeStr = r.completed_at 
            ? new Date(r.completed_at).toLocaleString('zh-TW', { 
                month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false 
              })
            : '-';
            
        const solTypeClass = r.solution_type === '更換' ? 'sol-replace' : r.solution_type === '維修' ? 'sol-repair' : '';
            
        const row = document.createElement('tr');
        row.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="export-checkbox" data-id="${r.id}" ${isChecked ? 'checked' : ''} onchange="toggleExportItem(this)">
            </td>
            <td><span class="status-label done">已完成</span></td>
            <td style="font-weight: 600; color: var(--primary);">${r.car_number}</td>
            <td><span class="sol-type-label ${solTypeClass}">${r.solution_type || '-'}</span></td>
            <td>${r.solution || '-'}</td>
            <td>${r.mileage || '-'} KM</td>
            <td>${r.handler_name || '-'}</td>
            <td>${completedTimeStr}</td>
        `;
        listBody.appendChild(row);
    });
    
    // 更新已選取筆數顯示
    selectedCountEl.innerText = visibleSelectedCount;
    
    // 同步導出 Master Checkbox 狀態
    const masterCheckbox = document.getElementById('export-select-all');
    if (masterCheckbox) {
        const allVisibleChecked = displayReports.length > 0 && displayReports.every(r => selectedExportIds.has(r.id));
        const someVisibleChecked = displayReports.some(r => selectedExportIds.has(r.id));
        masterCheckbox.checked = allVisibleChecked;
        masterCheckbox.indeterminate = someVisibleChecked && !allVisibleChecked;
    }
}

function toggleExportItem(el) {
    const id = el.getAttribute('data-id');
    if (el.checked) {
        selectedExportIds.add(id);
    } else {
        selectedExportIds.delete(id);
    }
    renderExportTable();
}

function toggleAllExportItems(masterEl) {
    const checked = masterEl.checked;
    
    const start = document.getElementById('export-start-date').value;
    const end = document.getElementById('export-end-date').value;
    const showReplace = document.getElementById('export-filter-replace').checked;
    const showRepair = document.getElementById('export-filter-repair').checked;
    const showDesign = document.getElementById('export-filter-design').checked;
    
    const displayReports = allReports.filter(r => {
        if (r.status !== '已完成') return false;
        
        if (r.completed_at) {
            const completedDate = r.completed_at.slice(0, 10);
            if (start && completedDate < start) return false;
            if (end && completedDate > end) return false;
        } else {
            return false;
        }
        
        const type = r.solution_type;
        if (type === '更換') return showReplace;
        if (type === '維修') return showRepair;
        if (type === '設計修改') return showDesign;
        return false;
    });
    
    displayReports.forEach(r => {
        if (checked) {
            selectedExportIds.add(r.id);
        } else {
            selectedExportIds.delete(r.id);
        }
    });
    
    renderExportTable();
}

async function triggerCustomExport(format) {
    const token = document.getElementById('admin-token').value;
    if (!token) return;
    
    const start = document.getElementById('export-start-date').value;
    const end = document.getElementById('export-end-date').value;
    const showReplace = document.getElementById('export-filter-replace').checked;
    const showRepair = document.getElementById('export-filter-repair').checked;
    const showDesign = document.getElementById('export-filter-design').checked;
    
    const targetReports = allReports.filter(r => {
        if (r.status !== '已完成') return false;
        if (!selectedExportIds.has(r.id)) return false;
        
        if (r.completed_at) {
            const completedDate = r.completed_at.slice(0, 10);
            if (start && completedDate < start) return false;
            if (end && completedDate > end) return false;
        } else {
            return false;
        }
        
        const type = r.solution_type;
        if (type === '更換') return showReplace;
        if (type === '維修') return showRepair;
        if (type === '設計修改') return showDesign;
        return false;
    });
    
    if (targetReports.length === 0) {
        showToast("請至少勾選一筆資料進行導出", "error");
        return;
    }
    
    // 獲取選擇的內容欄位 (處理方案 / 通報回覆)
    const contentFieldEl = document.querySelector('input[name="export-content-field"]:checked');
    const contentField = contentFieldEl ? contentFieldEl.value : 'solution';
    
    showToast("報表產生中，請稍候...", "success");
    
    if (format === 'pdf') {
        // "2.匯出pdf時,不同客運用不同pdf檔案,檔案名稱為客運名稱+月份"
        // Group by vendor and month
        const groups = {};
        targetReports.forEach(r => {
            let vendor = '未知客運';
            const car = (r.car_number || '').trim();
            if (monitoredBuses && monitoredBuses.length > 0) {
                const found = monitoredBuses.find(b => (b.plate_number || '').trim() === car);
                if (found) {
                    vendor = found.vendor_name || '未知客運';
                }
            }
            r.vendor_name = vendor;
            const month = r.completed_at ? r.completed_at.slice(0, 7) : '無日期'; // YYYY-MM
            const key = `${vendor}_${month}`;
            if (!groups[key]) {
                groups[key] = { vendor, month, ids: [] };
            }
            groups[key].ids.push(r.id);
        });
        
        let successCount = 0;
        for (const group of Object.values(groups)) {
            try {
                const response = await fetch('/admin/export/custom', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'token': token
                    },
                    body: JSON.stringify({
                        ids: group.ids,
                        format: 'pdf',
                        content_field: contentField
                    })
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || `匯出 ${group.vendor} PDF 失敗`);
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = `${group.vendor}_${group.month.replace('-', '年')}月.pdf`;
                if (contentDisposition) {
                    const matches = /filename\*=UTF-8''([^;]+)/.exec(contentDisposition);
                    if (matches && matches[1]) {
                        filename = decodeURIComponent(matches[1]);
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                successCount++;
            } catch (e) {
                console.error("Export Group Error:", e);
                showToast(e.message, "error");
            }
        }
        if (successCount > 0) {
            showToast(`成功匯出 ${successCount} 個 PDF 檔案！`);
        }
    } else {
        // Excel format
        try {
            const response = await fetch('/admin/export/custom', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'token': token
                },
                body: JSON.stringify({
                    ids: targetReports.map(r => r.id),
                    format: 'excel',
                    content_field: contentField
                })
            });
            
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "導出失敗");
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `維修通報報表_${new Date().toISOString().slice(0, 10)}.xlsx`;
            if (contentDisposition) {
                const matches = /filename\*=UTF-8''([^;]+)/.exec(contentDisposition);
                if (matches && matches[1]) {
                    filename = decodeURIComponent(matches[1]);
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            showToast("Excel 匯出成功！");
        } catch (e) {
            console.error("Export Error:", e);
            showToast(e.message, "error");
        }
    }
}

// ==========================================================================
// 品情統計分頁邏輯 (Tab: Quality Stats)
// ==========================================================================
let qualityChart = null;

async function loadQualityStats() {
    // 1. 初始化日期區間為當月 (如尚未設定)
    const startDateEl = document.getElementById('quality-start-date');
    const endDateEl = document.getElementById('quality-end-date');
    
    if (startDateEl && !startDateEl.value) {
        const now = new Date();
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
        const yyyy = firstDay.getFullYear();
        const mm = String(firstDay.getMonth() + 1).padStart(2, '0');
        startDateEl.value = `${yyyy}-${mm}-01`;
    }
    if (endDateEl && !endDateEl.value) {
        const now = new Date();
        const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        const yyyy = lastDay.getFullYear();
        const mm = String(lastDay.getMonth() + 1).padStart(2, '0');
        const dd = String(lastDay.getDate()).padStart(2, '0');
        endDateEl.value = `${yyyy}-${mm}-${dd}`;
    }

    const start = startDateEl ? startDateEl.value : '';
    const end = endDateEl ? endDateEl.value : '';

    // 取得類型勾選狀態
    const showReplace = document.getElementById('quality-type-replace').checked;
    const showRepair = document.getElementById('quality-type-repair').checked;
    const showDesign = document.getElementById('quality-type-design').checked;

    // 更新標題與說明文字
    const titleEl = document.getElementById('quality-title-month');
    if (titleEl) {
        if (start && end) {
            titleEl.innerText = `📊 品情統計 (${start} ~ ${end})`;
        } else {
            titleEl.innerText = `📊 品情統計`;
        }
    }

    const descEl = document.querySelector('#tab-quality .text-muted');
    if (descEl) {
        const activeTypes = [];
        if (showReplace) activeTypes.push('更換');
        if (showRepair) activeTypes.push('維修');
        if (showDesign) activeTypes.push('設計修改');
        const typeStr = activeTypes.length > 0 ? activeTypes.join('、') : '無';
        descEl.innerText = `統計範圍：${start || '不限'} 至 ${end || '不限'}，統計類型為「${typeStr}」之案件。`;
    }

    // 2. 篩選符合日期與類型的通報
    const filtered = allReports.filter(r => {
        const dateStr = r.completed_at || r.created_at;
        if (!dateStr) return false;
        const datePart = dateStr.slice(0, 10);
        if (start && datePart < start) return false;
        if (end && datePart > end) return false;

        const type = r.solution_type;
        if (type === '更換') return showReplace;
        if (type === '維修') return showRepair;
        if (type === '設計修改') return showDesign;
        return false;
    });

    // 3. 定義部件選項清單 (用於堆疊圖 Series)
    const componentsList = ["TMS", "動力", "BMS", "冷氣", "電子影像", "方向燈座", "車門", "車裝", "燈光", "底盤件", "儀錶", "其他", "未分類"];
    
    // 4. 初始化客運商統計資料結構
    const vendorStats = {};
    
    filtered.forEach(r => {
        // 解析客運商
        let vendor = '未知客運';
        const car = (r.car_number || '').trim();
        if (monitoredBuses && monitoredBuses.length > 0) {
            const found = monitoredBuses.find(b => (b.plate_number || '').trim() === car);
            if (found) {
                vendor = found.vendor_name || '未知客運';
            }
        }
        
        // 規範部件名稱
        let comp = (r.component || '').trim();
        if (!comp) {
            comp = '未分類';
        } else if (!componentsList.includes(comp)) {
            comp = '其他';
        }
        
        if (!vendorStats[vendor]) {
            vendorStats[vendor] = {
                vendor: vendor,
                replaceCount: 0,
                repairCount: 0,
                designCount: 0,
                totalCount: 0,
                componentCounts: {}
            };
            componentsList.forEach(c => {
                vendorStats[vendor].componentCounts[c] = 0;
            });
        }
        
        if (r.solution_type === '更換') {
            vendorStats[vendor].replaceCount++;
        } else if (r.solution_type === '維修') {
            vendorStats[vendor].repairCount++;
        } else if (r.solution_type === '設計修改') {
            vendorStats[vendor].designCount++;
        }
        vendorStats[vendor].totalCount++;
        vendorStats[vendor].componentCounts[comp]++;
    });

    // 轉為陣列並依「總累計件數」從高到低排序
    const vendorArray = Object.values(vendorStats);
    vendorArray.sort((a, b) => b.totalCount - a.totalCount);

    // 5. 渲染右側表格 (客運商累計件數)
    const tableBody = document.getElementById('quality-vendor-table-body');
    if (tableBody) {
        tableBody.innerHTML = '';
        if (vendorArray.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">所選日期區間與類型查無通報紀錄</td></tr>';
        } else {
            vendorArray.forEach(v => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600;">${v.vendor}</td>
                    <td style="text-align: center;">${v.replaceCount}</td>
                    <td style="text-align: center;">${v.repairCount}</td>
                    <td style="text-align: center;">${v.designCount}</td>
                    <td style="text-align: center; color: var(--primary); font-weight: bold;">${v.totalCount}</td>
                `;
                tableBody.appendChild(tr);
            });
        }
    }

    // 6. 渲染左側 ApexCharts 橫式堆疊圖
    const chartContainer = document.getElementById('quality-stacked-chart');
    if (!chartContainer) return;

    if (vendorArray.length === 0) {
        chartContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 5rem 0; font-size: 0.95rem;">所選條件尚無通報統計資料，無法產生圖表。</div>';
        if (qualityChart) {
            qualityChart.destroy();
            qualityChart = null;
        }
        return;
    }

    // Y 軸類別：排序後的客運商列表 (Y 軸從高到低，即陣列首項在最上方)
    const categories = vendorArray.map(v => v.vendor);

    // X 軸數據：每個部件作為一組 Series，長度與客運商列表相同
    const series = componentsList.map(comp => {
        return {
            name: comp,
            data: vendorArray.map(v => v.componentCounts[comp] || 0)
        };
    });

    // 過濾掉全為 0 的部件，保持圖例乾淨
    const activeSeries = series.filter(s => s.data.some(val => val > 0));

    const options = {
        series: activeSeries.length > 0 ? activeSeries : [{ name: '無資料', data: Array(categories.length).fill(0) }],
        chart: {
            type: 'bar',
            height: Math.max(350, categories.length * 45 + 100), // 動態自適應高度
            stacked: true,
            toolbar: { show: true },
            background: 'transparent'
        },
        plotOptions: {
            bar: {
                horizontal: true,
                dataLabels: {
                    total: {
                        enabled: true,
                        offsetX: 8,
                        style: {
                            fontSize: '12px',
                            fontWeight: 900,
                            colors: ['#fff']
                        }
                    }
                }
            }
        },
        colors: [
            '#3b82f6', // TMS (藍)
            '#f59e0b', // 動力 (黃)
            '#10b981', // BMS (綠)
            '#0ea5e9', // 冷氣 (淺藍)
            '#d946ef', // 電子影像 (洋紅)
            '#ec4899', // 方向燈座 (粉)
            '#8b5cf6', // 車門 (紫)
            '#06b6d4', // 車裝 (青)
            '#ef4444', // 燈光 (紅)
            '#14b8a6', // 底盤件 (藍綠)
            '#f97316', // 儀錶 (橘)
            '#6b7280', // 其他 (灰)
            '#9ca3af'  // 未分類 (淺灰)
        ],
        stroke: {
            width: 1,
            colors: ['var(--surface)']
        },
        xaxis: {
            categories: categories,
            labels: {
                style: { colors: '#94a3b8', fontSize: '11px' }
            },
            title: {
                text: '案件數量 (件)',
                style: { color: '#94a3b8', fontSize: '12px' }
            }
        },
        yaxis: {
            labels: {
                style: { colors: '#f1f5f9', fontSize: '12px', fontWeight: 'bold' }
            }
        },
        tooltip: {
            theme: 'dark',
            y: {
                formatter: function (val) {
                    return val + " 件";
                }
            }
        },
        fill: {
            opacity: 0.95
        },
        legend: {
            position: 'top',
            horizontalAlign: 'left',
            labels: { colors: '#94a3b8' },
            fontSize: '12px'
        },
        theme: { mode: 'dark' }
    };

    if (qualityChart) {
        qualityChart.destroy();
    }
    chartContainer.innerHTML = '';
    qualityChart = new ApexCharts(chartContainer, options);
    qualityChart.render();
}



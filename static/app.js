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

function renderReports() {
    const list = document.getElementById('report-list');
    list.innerHTML = '';

    const filteredReports = hideDone 
        ? allReports.filter(r => r.status !== '已完成')
        : allReports;

    if (filteredReports.length === 0) {
        list.innerHTML = '<tr><td colspan="7" class="loading-state">目前尚無通報記錄。</td></tr>';
        return;
    }

    filteredReports.forEach((report, index) => {
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
            <td><span class="sol-type-label ${solTypeClass}">${solType}</span></td>
            <td class="cell-mileage">${report.mileage || '-'}</td>
            <td>${report.handler_name || '-'}</td>
            <td class="cell-time">${createdTimeStr}</td>
            <td class="cell-time">${completedTimeStr}</td>
            <td class="table-actions">
                <button onclick="event.stopPropagation(); viewDetail('${report.id}')">詳情</button>
                ${report.status !== '已完成' ? `<button class="btn-primary" onclick="event.stopPropagation(); markDone('${report.id}')">完成</button>` : ''}
                <button class="btn-danger" onclick="event.stopPropagation(); deleteReport('${report.id}')">刪除</button>
            </td>
        `;
        list.appendChild(row);
    });
}

function viewDetail(id) {
    currentReportId = id;
    const report = allReports.find(r => r.id === id);
    if (!report) return;

    const modal = document.getElementById('modal');
    const body = document.getElementById('modal-body');
    const solutionDisplay = document.getElementById('solution-display');
    const solutionInput = document.getElementById('solution-input');
    
    // Set solution & mileage
    solutionDisplay.innerText = report.solution || "暫無處理紀錄";
    solutionInput.value = report.solution || "";
    document.getElementById('mileage-input').value = report.mileage || "";

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
                <h2 style="margin-bottom:1rem; color:var(--primary);">車號 # ${report.car_number}</h2>
                <div style="margin-bottom:1.5rem; display:flex; gap:.5rem; align-items:center;">
                    <span class="status-label ${report.status === '待處理' ? 'pending' : report.status === '維修中' ? 'progress' : 'done'}">${report.status}</span>
                    ${report.solution_type ? `<span class="sol-type-label ${report.solution_type === '更換' ? 'sol-replace' : 'sol-repair'}">${report.solution_type}</span>` : ''}
                </div>
            </div>
            
            <div class="detail-row">
                <label>通報時間 / 完成時間</label>
                <p>${new Date(report.created_at).toLocaleString('zh-TW')} / ${report.completed_at ? new Date(report.completed_at).toLocaleString('zh-TW') : '尚未完成'}</p>
            </div>
            
            <div class="detail-row">
                <label>目前里程</label>
                <p>${report.mileage ? report.mileage + ' KM' : '尚未填寫'}</p>
            </div>

            <div class="detail-row">
                <label>處理人員</label>
                <p>${report.handler_name || '尚未填寫'}</p>
            </div>

            <div class="detail-row">
                <label>問題描述</label>
                <p>${report.description}</p>
            </div>

            ${mediaHtml}

            <div class="modal-actions">
                ${report.status === '待處理' ? `<button class="btn-primary" onclick="updateStatus('${id}', '維修中')">進入維修</button>` : ''}
                ${report.status !== '已完成' ? `<button class="btn-primary" onclick="markDone('${id}')">完成維修並通知</button>` : ''}
                <button class="btn-secondary" onclick="closeModal()">關閉</button>
            </div>
        </div>
    `;
    modal.classList.remove('hidden');
}

async function saveSolution() {
    if (!currentReportId) return;
    const solution = document.getElementById('solution-input').value.trim();
    const mileage = document.getElementById('mileage-input').value.trim();
    
    if (!solution) {
        showToast("請輸入方案內容", "error");
        return;
    }

    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${currentReportId}/solution`, {
            method: 'PATCH',
            headers: { 
                'token': token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ solution, mileage })
        });
        if (response.ok) {
            showToast("方案與里程已儲存");
            // Update local data
            allReports = allReports.map(r => r.id === currentReportId ? { ...r, solution, mileage } : r);
            document.getElementById('solution-display').innerText = solution;
            renderReports(); // Refresh table to show new mileage
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
    document.getElementById('count-pending').innerText = allReports.filter(r => r.status === '待處理').length;
    document.getElementById('count-in-progress').innerText = allReports.filter(r => r.status === '維修中').length;
    document.getElementById('count-done').innerText = allReports.filter(r => r.status === '已完成').length;
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

    showToast("報表產生中，請稍候...", "success");

    try {
        const response = await fetch(`/admin/export?type=${type}&start=${start}&end=${end}`, {
            headers: { 'token': token }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "導出失敗");
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type === 'report' ? '通報紀錄' : '換件紀錄'}_${start}_${end}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        showToast("下載成功", "success");
        closeExportModal();
    } catch (error) {
        showToast(error.message, "error");
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

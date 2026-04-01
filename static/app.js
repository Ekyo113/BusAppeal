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
        list.innerHTML = '<tr><td colspan="6" class="loading-state">目前尚無通報記錄。</td></tr>';
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
        const timeStr = new Date(report.created_at).toLocaleString('zh-TW', { 
            month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false 
        });

        row.innerHTML = `
            <td class="row-index">${index + 1}</td>
            <td><span class="status-label ${statusClass}">${report.status}</span></td>
            <td class="cell-car">${report.car_number}</td>
            <td class="cell-desc">${report.description}</td>
            <td class="cell-time">${timeStr}</td>
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
    
    // Set solution
    solutionDisplay.innerText = report.solution || "暫無處理紀錄";
    solutionInput.value = report.solution || "";

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
                <div style="margin-bottom:1.5rem">
                    <span class="status-label ${report.status === '待處理' ? 'pending' : report.status === '維修中' ? 'progress' : 'done'}">${report.status}</span>
                </div>
            </div>
            
            <div class="detail-row">
                <label>通報時間</label>
                <p>${new Date(report.created_at).toLocaleString('zh-TW')}</p>
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
            body: JSON.stringify({ solution })
        });
        if (response.ok) {
            showToast("方案已儲存");
            // Update local data
            allReports = allReports.map(r => r.id === currentReportId ? { ...r, solution } : r);
            document.getElementById('solution-display').innerText = solution;
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

async function updateStatus(id, status) {
    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${id}`, {
            method: 'PATCH',
            headers: { 
                'token': token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status })
        });
        if (response.ok) {
            allReports = allReports.map(r => r.id === id ? { ...r, status } : r);
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
    if (!confirm("確定維修完成並要通知駕駛嗎？")) return;
    
    const token = document.getElementById('admin-token').value;
    try {
        const response = await fetch(`/admin/reports/${id}/notify`, {
            method: 'POST',
            headers: { 'token': token }
        });
        
        if (response.ok) {
            await updateStatus(id, '已完成');
            showToast("已更新狀態並發送通知！");
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

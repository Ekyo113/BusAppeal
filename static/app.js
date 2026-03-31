let allReports = [];

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
        reportList.innerHTML = '<div class="loading-state"><p>載入失敗，請重新整理頁面。</p></div>';
    }
}

function renderReports() {
    const list = document.getElementById('report-list');
    list.innerHTML = '';

    if (allReports.length === 0) {
        list.innerHTML = '<div class="loading-state"><p>目前尚無任何通報記錄。</p></div>';
        return;
    }

    allReports.forEach(report => {
        const card = document.createElement('div');
        card.className = 'report-card';
        card.setAttribute('data-status', report.status);
        
        const statusMap = {
            '待處理': 'pending',
            '維修中': 'progress',
            '已完成': 'done'
        };
        const statusClass = statusMap[report.status] || 'pending';
        const mediaCount = report.media_urls ? report.media_urls.length : 0;
        const timeStr = new Date(report.created_at).toLocaleString('zh-TW', { hour12: false });

        card.innerHTML = `
            <div class="card-header">
                <span class="car-id"># ${report.car_number}</span>
                <span class="status-label ${statusClass}">${report.status}</span>
            </div>
            <div class="card-body">
                <h3>${report.description.substring(0, 40)}${report.description.length > 40 ? '...' : ''}</h3>
                <div class="card-meta">
                    <p>🕒 ${timeStr}</p>
                    <p>📸 ${mediaCount} 個媒體檔案</p>
                </div>
            </div>
            <div class="card-footer">
                <button onclick="viewDetail('${report.id}')">詳情</button>
                ${report.status !== '已完成' ? `<button class="btn-primary" onclick="markDone('${report.id}')">完成維修</button>` : ''}
            </div>
        `;
        list.appendChild(card);
    });
}

function updateStats() {
    document.getElementById('count-pending').innerText = allReports.filter(r => r.status === '待處理').length;
    document.getElementById('count-in-progress').innerText = allReports.filter(r => r.status === '維修中').length;
    document.getElementById('count-done').innerText = allReports.filter(r => r.status === '已完成').length;
}

function viewDetail(id) {
    const report = allReports.find(r => r.id === id);
    const modal = document.getElementById('modal');
    const body = document.getElementById('modal-body');

    let mediaHtml = '';
    if (report.media_urls && report.media_urls.length > 0) {
        mediaHtml = `
            <div class="media-container">
                <label>相關相片/影片</label>
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
            <h2>通報詳情 - 車號 ${report.car_number}</h2>
            
            <div class="detail-row">
                <label>通報日期與時間</label>
                <p>${new Date(report.created_at).toLocaleString()}</p>
            </div>
            
            <div class="detail-row">
                <label>問題描述</label>
                <p>${report.description}</p>
            </div>

            <div class="detail-row">
                <label>目前狀態</label>
                <p><strong>${report.status}</strong></p>
            </div>

            ${mediaHtml}

            <div class="modal-actions">
                ${report.status !== '待處理' ? `<button onclick="updateStatus('${id}', '待處理')">設為待處理</button>` : ''}
                ${report.status !== '維修中' ? `<button onclick="updateStatus('${id}', '維修中')">設為維修中</button>` : ''}
                ${report.status !== '已完成' ? `<button class="btn-primary" onclick="markDone('${id}')">維修完成並通知</button>` : ''}
            </div>
        </div>
    `;
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Prevent scroll
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
            // Success
            allReports = allReports.map(r => r.id === id ? { ...r, status } : r);
            renderReports();
            updateStats();
            if (document.getElementById('modal').classList.contains('hidden') === false) {
                viewDetail(id); // Refresh detail view
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
    // document.body.style.overflow = 'auto'; // Remove to avoid Safari issues
}

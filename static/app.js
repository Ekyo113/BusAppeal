let allReports = [];

async function loadReports() {
    const token = document.getElementById('admin-token').value;
    if (!token) {
        alert("請輸入管理金鑰！");
        return;
    }

    const reportList = document.getElementById('report-list');
    reportList.innerHTML = '<div class="loading">載入中...</div>';

    try {
        const response = await fetch('/admin/reports', {
            headers: { 'token': token }
        });

        if (response.status === 401) {
            alert("金鑰錯誤！");
            reportList.innerHTML = '<div class="loading">驗證失敗，請重試。</div>';
            return;
        }

        allReports = await response.json();
        renderReports();
        updateStats();
    } catch (error) {
        console.error(error);
        alert("載入失敗，請檢查伺服器或網路。");
    }
}

function renderReports() {
    const list = document.getElementById('report-list');
    list.innerHTML = '';

    allReports.forEach(report => {
        const card = document.createElement('div');
        card.className = 'report-card';
        
        const statusClass = {
            '待處理': 'status-pending',
            '維修中': 'status-progress',
            '已完成': 'status-done'
        }[report.status] || '';

        const mediaCount = report.media_urls ? report.media_urls.length : 0;

        card.innerHTML = `
            <span class="status-badge ${statusClass}">${report.status}</span>
            <span class="car-badge">${report.car_number}</span>
            <div class="summary">${report.ai_summary}</div>
            <div class="media-count">📸 ${mediaCount} 個媒體</div>
            <div class="actions">
                <button onclick="viewDetail('${report.id}')">查看詳情</button>
                ${report.status !== '已完成' ? `<button class="btn-notify" onclick="markDone('${report.id}')">標記完成並通知</button>` : ''}
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
        mediaHtml = '<div class="media-grid">';
        report.media_urls.forEach(url => {
            if (url.toLowerCase().endsWith('.mp4')) {
                mediaHtml += `<video src="${url}" controls></video>`;
            } else {
                mediaHtml += `<img src="${url}" onclick="window.open('${url}')">`;
            }
        });
        mediaHtml += '</div>';
    }

    body.innerHTML = `
        <h2>通報詳情 - ${report.car_number}</h2>
        <p><strong>時間：</strong>${new Date(report.created_at).toLocaleString()}</p>
        <p><strong>原始描述：</strong>${report.description}</p>
        <hr>
        <p><strong>AI 摘要：</strong>${report.ai_summary}</p>
        ${mediaHtml}
        <div class="actions" style="margin-top: 2rem;">
            <button onclick="updateStatus('${id}', '待處理')">設為待處理</button>
            <button onclick="updateStatus('${id}', '維修中')">設為維修中</button>
        </div>
    `;
    modal.classList.remove('hidden');
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
            closeModal();
            loadReports();
        }
    } catch (error) {
        alert("更新失敗");
    }
}

async function markDone(id) {
    if (!confirm("確定維修完成並要通知駕駛嗎？")) return;
    
    const token = document.getElementById('admin-token').value;
    try {
        // Update status
        await updateStatus(id, '已完成');
        // Send notification
        await fetch(`/admin/reports/${id}/notify`, {
            method: 'POST',
            headers: { 'token': token }
        });
        alert("已更新狀態並發送 Line 通知！");
    } catch (error) {
        alert("操作失敗，但狀態可能已更新。");
    }
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

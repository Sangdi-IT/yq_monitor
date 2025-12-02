document.getElementById('start').addEventListener('click', async () => {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
	const interval = document.getElementById('clickInterval').value;

	// 使用 chrome.tabs.sendMessage 替代 window.postMessage
	chrome.tabs.sendMessage(tab.id, {
		type: 'START_CLICKING',
		interval: parseInt(interval)
	});
	document.getElementById('currentStatus').textContent = '运行中';
});

document.getElementById('stop').addEventListener('click', async () => {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
	chrome.tabs.sendMessage(tab.id, { type: 'STOP_CLICKING' });
	document.getElementById('currentStatus').textContent = '已停止';
});

// 更新点击计数
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
	if (request.type === 'CLICK_COUNT') {
		const countElement = document.getElementById('clickCount');
		if (countElement) {
			const currentCount = parseInt(countElement.textContent || '0');
			countElement.textContent = currentCount + 1;
		}
	}
});
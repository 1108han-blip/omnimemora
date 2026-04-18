package api

func buildGatewayAlertHTML(gatewayStatus gatewayStatusPayload) string {
	if gatewayStatus.Status == "healthy" {
		return ""
	}

	html := `		<div class="gateway-alert">
			<strong>Gateway status: ` + escapeHTML(gatewayStatus.Status) + `</strong>
			<div>Recommended action: ` + escapeHTML(gatewayStatus.RecommendedAction) + `</div>
`
	if gatewayStatus.UserActionRequired {
		html += `			<div>User decision required before changing install state.</div>
			<div>Internal actions: POST /gateway/decision/disable-route or POST /gateway/decision/uninstall with {"family_id":"..."}</div>
			<div style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
				<label for="gateway-action-family" style="font-size: 13px;">Family ID:</label>
				<input id="gateway-action-family" type="text" value="claude_code" style="padding: 6px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.08); color: #fff; min-width: 160px;" />
				<button type="button" onclick="runGatewayAction('disable-route')" style="padding: 6px 10px; border-radius: 6px; border: none; cursor: pointer;">Disable Route</button>
				<button type="button" onclick="runGatewayAction('uninstall')" style="padding: 6px 10px; border-radius: 6px; border: none; cursor: pointer;">Uninstall</button>
			</div>
			<div id="gateway-action-result" style="margin-top: 8px; font-size: 12px; opacity: 0.9;"></div>
`
	}
	if gatewayStatus.ErrorCode != "" {
		html += `			<div>Error code: ` + escapeHTML(gatewayStatus.ErrorCode) + `</div>
`
	}
	html += `		</div>
`
	return html
}

func gatewayActionScriptHTML() string {
	return `	<script>
	async function runGatewayAction(action) {
		const familyInput = document.getElementById('gateway-action-family');
		const result = document.getElementById('gateway-action-result');
		if (!familyInput || !result) return;
		const familyId = (familyInput.value || '').trim();
		if (!familyId) {
			result.textContent = 'family_id is required';
			return;
		}
		result.textContent = 'Running ' + action + '...';
		try {
			const response = await fetch('/gateway/decision/' + action, {
				method: 'POST',
				headers: {'Content-Type': 'application/json'},
				body: JSON.stringify({family_id: familyId})
			});
			const payload = await response.json();
			if (!response.ok) {
				result.textContent = 'Failed: ' + (payload.error || payload.code || response.status);
				return;
			}
			result.textContent = 'Applied: ' + (payload.message || action);
		} catch (err) {
			result.textContent = 'Failed: ' + err;
		}
	}
	</script>
`
}

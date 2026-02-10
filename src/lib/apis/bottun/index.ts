import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getUIConfig = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/bottun/config/init`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.log(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getDimensionValues = async (
	token: string,
	kpi: string,
	dimensionType: string,
	currentSelection: string[] = []
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/bottun/config/dimension`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			kpi: kpi,
			dimension_type: dimensionType,
			current_selection: currentSelection
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.log(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const analyzeQuery = async (token: string, query: string, context: any = null) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/bottun/chat/analyze`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			query: query,
			context: context
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.log(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const generateAndExecuteSQL = async (
	token: string,
	kpi: string,
	timeRange: string,
	scope: string[]
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/bottun/chat/sql`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			kpi: kpi,
			time_range: timeRange,
			scope: scope
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.log(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getDownloadUrl = (kpi: string, timeRange: string, scope: string[]) => {
	const params = new URLSearchParams();
	params.append('kpi', kpi);
	if (timeRange) params.append('time_range', timeRange);
	scope.forEach((s) => params.append('scope', s));
	return `${WEBUI_API_BASE_URL}/bottun/chat/download/get?${params.toString()}`;
};

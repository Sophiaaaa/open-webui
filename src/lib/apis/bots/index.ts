import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getBotsAccess = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/bots/access`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};


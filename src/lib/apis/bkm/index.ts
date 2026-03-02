export type BkmRankedText = {
	id: string;
	text: string;
	score: number;
};

export type BkmDocHit = {
	pdf: string;
	page: number | null;
	title: string;
	score: number;
	snippet: string;
};

export type BkmAskResponse = {
	query: string;
	answer_markdown: string;
	causes: BkmRankedText[];
	actions: BkmRankedText[];
	docs_by_item: Record<string, BkmDocHit[]>;
	assets_base_url?: string;
	action_suggestion_min_score?: number;
};

export const getBkmStatus = async () => {
	let error = null;

		const res = await fetch(`/bkm/config/status`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json'
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

export const askBkm = async (token: string, query: string, topK: number = 5): Promise<BkmAskResponse> => {
	let error = null;

		const res = await fetch(`/bkm/chat/ask`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: token ? `Bearer ${token}` : ''
		},
		body: JSON.stringify({
			query,
			top_k: topK
		})
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

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	type ItemRating = 'up' | 'down' | null;

	type BkmRankedText = {
		id: string;
		text: string;
		score: number;
	};

	type BkmDocHit = {
		pdf: string;
		page: number | null;
		title: string;
		score: number;
		snippet: string;
	};

	export let message: any;
	export let isBot: boolean = false;
	export let selectedItemId: string | null = null;
	export let itemRatings: Record<string, ItemRating> = {};

	let introText = '';
	let pairedItems: { idx: number; cause: BkmRankedText | null; action: BkmRankedText | null }[] = [];
	const DEFAULT_ACTION_SUGGESTION_MIN_SCORE = 0.75;
	let actionSuggestionMinScore = DEFAULT_ACTION_SUGGESTION_MIN_SCORE;

	const dispatch = createEventDispatcher();

	$: introText = typeof message?.answer_markdown === 'string' ? (message.answer_markdown.split('\n')[0] || '') : '';
	$: actionSuggestionMinScore =
		typeof message?.action_suggestion_min_score === 'number'
			? message.action_suggestion_min_score
			: DEFAULT_ACTION_SUGGESTION_MIN_SCORE;

	$: pairedItems = (() => {
		const causes = Array.isArray(message?.causes) ? message.causes : [];
		const actions = Array.isArray(message?.actions) ? message.actions : [];
		const n = Math.max(causes.length, actions.length);
		return Array.from({ length: n }, (_, idx) => ({
			idx,
			cause: causes[idx] ?? null,
			action: actions[idx] ?? null
		})).filter((pair) => shouldShowPair(pair.cause, pair.action));
	})();

	function shouldShowCause(cause: BkmRankedText | null): boolean {
		if (!cause) return false;
		const score = typeof cause.score === 'number' ? cause.score : 0;
		return score >= actionSuggestionMinScore;
	}

	function shouldShowPair(cause: BkmRankedText | null, action: BkmRankedText | null): boolean {
		return shouldShowCause(cause) || shouldShowAction(action, cause);
	}

	function getDocsForEntryIds(entryIds: string[]): BkmDocHit[] {
		const seen = new Set<string>();
		const docs: BkmDocHit[] = [];
		for (const entryId of entryIds) {
			const hits = (message?.docs_by_item?.[entryId] as BkmDocHit[]) || [];
			for (const h of hits) {
				const key = `${h?.pdf ?? ''}#${h?.page ?? ''}`;
				if (seen.has(key)) continue;
				seen.add(key);
				docs.push(h);
			}
		}
		return docs;
	}

	function handleSelect(kind: 'cause' | 'action', entry: BkmRankedText) {
		const docs = getDocsForEntryIds([entry.id]);
		dispatch('selectItem', { kind, entry, docs });
	}

	function handleSelectPair(pair: { cause: BkmRankedText | null; action: BkmRankedText | null }) {
		const primary = pair.cause ?? pair.action;
		if (!primary) return;
		const kind: 'cause' | 'action' = pair.cause ? 'cause' : 'action';
		const entryIds = [
			shouldShowCause(pair.cause) ? pair.cause?.id : null,
			shouldShowAction(pair.action, pair.cause) ? pair.action?.id : null
		].filter(Boolean) as string[];
		const docs = getDocsForEntryIds(entryIds);
		dispatch('selectItem', { kind, entry: primary, docs });
	}

	function shouldShowAction(action: BkmRankedText | null, cause: BkmRankedText | null): boolean {
		if (!action) return false;
		if (!cause) return true;
		const score = typeof action.score === 'number' ? action.score : 0;
		return score >= actionSuggestionMinScore;
	}

	function dispatchItemRating(payload: { kind: 'cause' | 'action'; entry: BkmRankedText; rating: ItemRating }) {
		const docs = (message?.docs_by_item?.[payload.entry.id] as BkmDocHit[]) || [];
		dispatch('rateItem', { ...payload, docs });
	}

	function handlePairRate(
		e: MouseEvent,
		pair: { cause: BkmRankedText | null; action: BkmRankedText | null },
		rating: ItemRating
	) {
		e.preventDefault();
		e.stopPropagation();
		if (pair.cause && shouldShowCause(pair.cause))
			dispatchItemRating({ kind: 'cause', entry: pair.cause, rating });
		if (pair.action && shouldShowAction(pair.action, pair.cause))
			dispatchItemRating({ kind: 'action', entry: pair.action, rating });
	}
</script>

<div class="flex w-full {isBot ? 'justify-start' : 'justify-end'} mb-4">
	<div
		class="max-w-[92%] p-4 rounded-lg {isBot ? 'bg-white border border-gray-200' : 'bg-blue-600 text-white'} shadow-sm"
	>
		{#if !isBot}
			<div class="text-sm whitespace-pre-wrap break-words">{message.content}</div>
		{:else}
			{#if introText}
				<div class="text-sm text-gray-800 whitespace-pre-wrap break-words">{introText}</div>
			{/if}
			{#if message.error}
				<div class="mt-2 text-sm text-red-600">{message.error}</div>
			{/if}

			{#if pairedItems && pairedItems.length > 0}
				<div class="mt-3">
					<div class="text-sm font-semibold text-gray-900">原因 / 行动建议:</div>
					<div class="mt-2 space-y-2">
						{#each pairedItems as pair}
							{@const pairRating =
								(pair.cause && pair.action && itemRatings[pair.cause.id] === itemRatings[pair.action.id]
									? itemRatings[pair.cause.id]
									: pair.cause
										? itemRatings[pair.cause.id]
										: pair.action
											? itemRatings[pair.action.id]
											: null) ?? null}
						<div class="flex items-center gap-2">
								<div
									role="button"
									tabindex="0"
									class="flex-1 text-left rounded-md border px-3 py-2 transition cursor-pointer {selectedItemId === (pair.cause?.id ?? pair.action?.id) ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}"
									on:click={() => handleSelectPair(pair)}
									on:keydown={(e) => {
										if (e.key === 'Enter') handleSelectPair(pair);
									}}
								>
									<div class="space-y-1">
										{#if shouldShowCause(pair.cause)}
											<div class="text-sm text-gray-900 break-words">
												<span class="font-semibold">原因：</span>{pair.cause?.text}
											</div>
										{/if}
									{#if shouldShowAction(pair.action, pair.cause)}
										<div class="text-sm text-gray-900 break-words">
											<span class="font-semibold">行动建议：</span>{pair.action?.text}
										</div>
									{/if}
									</div>
								</div>

								<div class="shrink-0 flex items-center gap-2">
									<button
										type="button"
										aria-label="点赞"
										class="px-2 py-1 rounded text-xs border {pairRating === 'up' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
										on:click={(e) => handlePairRate(e, pair, 'up')}
									>
										👍
									</button>
									<button
										type="button"
										aria-label="点踩"
										class="px-2 py-1 rounded text-xs border {pairRating === 'down' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
										on:click={(e) => handlePairRate(e, pair, 'down')}
									>
										👎
									</button>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		{/if}
	</div>
</div>

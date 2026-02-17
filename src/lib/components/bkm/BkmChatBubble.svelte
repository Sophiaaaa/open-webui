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

	const dispatch = createEventDispatcher();

	$: introText = typeof message?.answer_markdown === 'string' ? (message.answer_markdown.split('\n')[0] || '') : '';

	function handleSelect(kind: 'cause' | 'action', entry: BkmRankedText) {
		const docs = (message?.docs_by_item?.[entry.id] as BkmDocHit[]) || [];
		dispatch('selectItem', { kind, entry, docs });
	}

	function handleRate(
		e: MouseEvent,
		payload: { kind: 'cause' | 'action'; entry: BkmRankedText; rating: ItemRating }
	) {
		e.preventDefault();
		e.stopPropagation();
		const docs = (message?.docs_by_item?.[payload.entry.id] as BkmDocHit[]) || [];
		dispatch('rateItem', { ...payload, docs });
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

			{#if (message.causes && message.causes.length > 0) || (message.actions && message.actions.length > 0)}
				<div class="mt-3 space-y-4">
					{#if message.causes && message.causes.length > 0}
						<div>
							<div class="text-sm font-semibold text-gray-900">原因:</div>
							<div class="mt-2 space-y-2">
								{#each message.causes as entry}
									<div
										role="button"
										tabindex="0"
										class="w-full text-left rounded-md border px-3 py-2 transition cursor-pointer {selectedItemId === entry.id ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}"
										on:click={() => handleSelect('cause', entry)}
										on:keydown={(e) => {
											if (e.key === 'Enter') handleSelect('cause', entry);
										}}
									>
										<div class="flex items-center justify-between gap-3">
											<div class="min-w-0">
												<div class="text-sm text-gray-900 break-words">{entry.text}</div>
											</div>
											<div class="shrink-0 flex items-center gap-2">
												<button
													type="button"
													class="px-2 py-1 rounded text-xs border {itemRatings[entry.id] === 'up' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
													on:click={(e) => handleRate(e, { kind: 'cause', entry, rating: 'up' })}
												>
													赞
												</button>
												<button
													type="button"
													class="px-2 py-1 rounded text-xs border {itemRatings[entry.id] === 'down' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
													on:click={(e) => handleRate(e, { kind: 'cause', entry, rating: 'down' })}
												>
													踩
												</button>
											</div>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/if}

					{#if message.actions && message.actions.length > 0}
						<div>
							<div class="text-sm font-semibold text-gray-900">行动建议:</div>
							<div class="mt-2 space-y-2">
								{#each message.actions as entry}
									<div
										role="button"
										tabindex="0"
										class="w-full text-left rounded-md border px-3 py-2 transition cursor-pointer {selectedItemId === entry.id ? 'border-blue-300 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}"
										on:click={() => handleSelect('action', entry)}
										on:keydown={(e) => {
											if (e.key === 'Enter') handleSelect('action', entry);
										}}
									>
										<div class="flex items-center justify-between gap-3">
											<div class="min-w-0">
												<div class="text-sm text-gray-900 break-words">{entry.text}</div>
											</div>
											<div class="shrink-0 flex items-center gap-2">
												<button
													type="button"
													class="px-2 py-1 rounded text-xs border {itemRatings[entry.id] === 'up' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
													on:click={(e) => handleRate(e, { kind: 'action', entry, rating: 'up' })}
												>
													赞
												</button>
												<button
													type="button"
													class="px-2 py-1 rounded text-xs border {itemRatings[entry.id] === 'down' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}"
													on:click={(e) => handleRate(e, { kind: 'action', entry, rating: 'down' })}
												>
													踩
												</button>
											</div>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>

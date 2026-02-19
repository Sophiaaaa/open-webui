<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { askBkm, type BkmAskResponse, type BkmDocHit } from '$lib/apis/bkm';
	import { createNewFeedback } from '$lib/apis/evaluations';
	import BkmChatBubble from '$lib/components/bkm/BkmChatBubble.svelte';
	import { toast } from 'svelte-sonner';

	type ItemRating = 'up' | 'down' | null;

	let token = '';
	let messages: any[] = [];
	let userInput = '';
	let isLoading = false;
	let chatContainer: HTMLElement;

	let selectedItemId: string | null = null;
	let selectedDocs: BkmDocHit[] = [];
	let selectedDoc: BkmDocHit | null = null;
	let itemRatings: Record<string, ItemRating> = {};

	let activeTab: 'chat' | 'source' = 'chat';

	$: pdfUrl = selectedDoc?.pdf
		? `${selectedDoc.pdf ? `/bkm/assets/${encodeURIComponent(selectedDoc.pdf)}` : ''}${selectedDoc.page ? `#page=${selectedDoc.page}` : ''}`
		: '';

	function scrollToBottom() {
		if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
	}

	function resetChat() {
		selectedItemId = null;
		selectedDocs = [];
		selectedDoc = null;
		itemRatings = {};
		messages = [
			{
				id: crypto.randomUUID(),
				isBot: true,
				answer_markdown:
					'你好！我是 BKM 助手。请直接输入问题（我会从 BKM JSON+PDF 中检索原因/行动建议，并提供对应的 PDF 页码链接）。',
				causes: [],
				actions: [],
				docs_by_item: {}
			}
		];
	}

	onMount(async () => {
		token = localStorage.getItem('token') || '';
		resetChat();
	});

	async function sendMessage() {
		const content = (userInput || '').trim();
		if (!content || isLoading) return;

		messages = [...messages, { id: crypto.randomUUID(), isBot: false, content }];
		userInput = '';
		isLoading = true;
		await tick();
		scrollToBottom();

		try {
			const res: BkmAskResponse = await askBkm(token, content, 5);
			const botMsg: any = {
				id: crypto.randomUUID(),
				isBot: true,
				...res
			};
			messages = [...messages, botMsg];
		} catch (e: any) {
			messages = [
				...messages,
				{
					id: crypto.randomUUID(),
					isBot: true,
					error: e?.detail || e?.message || '请求失败',
					causes: [],
					actions: [],
					docs_by_item: {},
					answer_markdown: ''
				}
			];
		} finally {
			isLoading = false;
			await tick();
			scrollToBottom();
		}
	}

	async function handleRateItem(event: CustomEvent) {
		const { kind, entry, rating, docs } = event.detail as {
			kind: 'cause' | 'action';
			entry: { id: string; text: string; score: number };
			rating: ItemRating;
			docs?: BkmDocHit[];
		};
		if (!token) {
			toast.error('请先登录再反馈');
			return;
		}
		if (!rating) return;

		itemRatings = { ...itemRatings, [entry.id]: rating };
		try {
			await createNewFeedback(token, {
				type: 'bkm_item_rating',
				data: {
					rating,
					kind,
					entry_id: entry.id,
					text: entry.text,
					score: entry.score
				},
				meta: {
					page: 'bkm',
					docs: docs || []
				}
			});
			toast.success(rating === 'up' ? '已点赞' : '已点踩');
		} catch (e: any) {
			toast.error(e?.detail || e?.message || '反馈提交失败');
		}
	}

	function handleSelectItem(event: CustomEvent) {
		const { entry, docs } = event.detail as {
			kind: 'cause' | 'action';
			entry: { id: string; text: string; score: number };
			docs: BkmDocHit[];
		};
		selectedItemId = entry.id;
		selectedDocs = docs || [];
		selectedDoc = (docs && docs.length > 0 ? docs[0] : null) as any;
		activeTab = 'source';
	}

	function handleOpenDoc(doc: BkmDocHit) {
		selectedDoc = doc;
		activeTab = 'source';
	}

	function openPdfInNewTab() {
		if (!selectedDoc?.pdf) return;
		const url = `/bkm/assets/${encodeURIComponent(selectedDoc.pdf)}${selectedDoc.page ? `#page=${selectedDoc.page}` : ''}`;
		window.open(url, '_blank');
	}
</script>

<div class="h-full flex flex-col bg-gray-50 max-h-[calc(100vh-64px)]">
	<div class="bg-white border-b px-4 py-3 flex justify-between items-center shadow-sm shrink-0">
		<div class="min-w-0">
			<h1 class="font-bold text-lg text-gray-800 truncate">BKM Bot</h1>
			<div class="text-xs text-gray-500 truncate">基于 BKM JSON+PDF 的 action / root cause 问答</div>
		</div>
		<div class="flex items-center gap-2">
			<button class="text-sm text-gray-600 hover:text-blue-600" on:click={resetChat}>⟳ 重置对话</button>
			<button
				class="text-sm text-gray-600 hover:text-blue-600 lg:hidden"
				on:click={() => (activeTab = activeTab === 'chat' ? 'source' : 'chat')}
			>
				{activeTab === 'chat' ? '打开来源' : '返回对话'}
			</button>
		</div>
	</div>

	<div class="flex-1 overflow-hidden p-4">
		<div class="h-full grid grid-cols-1 lg:grid-cols-[minmax(520px,1fr)_520px] gap-4">
			<div class="h-full flex flex-col {activeTab !== 'chat' ? 'hidden lg:flex' : ''}">
				<div class="flex-1 overflow-y-auto" bind:this={chatContainer}>
					{#each messages as msg}
						<BkmChatBubble
							message={msg}
							isBot={msg.isBot}
							selectedItemId={selectedItemId}
							itemRatings={itemRatings}
							on:selectItem={handleSelectItem}
							on:rateItem={handleRateItem}
						/>
					{/each}

					{#if isLoading}
						<div class="flex w-full justify-start mb-4">
							<div class="bg-white p-3 rounded-lg border shadow-sm">
								<span class="animate-pulse">...</span>
							</div>
						</div>
					{/if}
				</div>

				<div class="bg-white border-t p-4 shrink-0">
					<div class="flex gap-2 items-end">
						<textarea
							class="flex-1 border rounded-md p-2 text-sm resize-none min-h-[44px] max-h-[160px]"
							bind:value={userInput}
							placeholder="请输入你的问题…"
							on:keydown={(e) => {
								if (e.key === 'Enter' && !e.shiftKey) {
									e.preventDefault();
									sendMessage();
								}
							}}
						/>
						<button
							class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm disabled:opacity-50"
							disabled={isLoading}
							on:click={sendMessage}
						>
							发送
						</button>
					</div>
					<div class="mt-2 text-xs text-gray-500">
						Enter 发送，Shift+Enter 换行
					</div>
				</div>
			</div>

			{#if selectedItemId}
				<div class="h-full {activeTab !== 'source' ? 'hidden lg:flex' : ''} flex flex-col">
					<div class="bg-white border rounded-lg overflow-hidden flex flex-col h-full">
						<div class="px-3 py-2 border-b flex items-center justify-between">
							<div class="flex items-center gap-2">
								<div class="text-sm font-semibold text-gray-900">搜索网页</div>
								<div class="text-xs text-gray-500">{selectedDocs?.length ?? 0}</div>
							</div>
							<div class="flex items-center gap-2">
							{#if selectedDoc?.pdf}
								<button
									class="text-xs px-2 py-1 border rounded hover:bg-gray-50"
									on:click={openPdfInNewTab}
								>
									在新标签页打开
								</button>
							{/if}
						</div>
					</div>

					<div class="border-b bg-white">
						{#if selectedItemId && selectedDocs && selectedDocs.length > 0}
							<div class="divide-y divide-gray-100">
								{#each selectedDocs as d}
									<button
										type="button"
										class="w-full text-left px-3 py-2 hover:bg-gray-50 {selectedDoc && selectedDoc.pdf === d.pdf && selectedDoc.page === d.page ? 'bg-blue-50' : ''}"
										on:click={() => handleOpenDoc(d)}
									>
										<div class="flex items-center justify-between gap-3">
											<div class="text-xs text-gray-500 truncate">{d.pdf}{d.page ? ` · 第 ${d.page} 页` : ''}</div>
											<div class="shrink-0 text-xs text-gray-500">{Math.round((d.score || 0) * 100)}%</div>
										</div>
										<div class="mt-1 text-sm font-semibold text-gray-900 break-words">{d.title || d.pdf}</div>
										{#if d.snippet}
											<div class="mt-1 text-xs text-gray-600 line-clamp-3 break-words">{d.snippet}</div>
										{/if}
									</button>
								{/each}
							</div>
						{:else}
							<div class="p-3 text-sm text-gray-500">点击左侧某组原因/行动建议后，这里会显示对应的 PDF 页码链接。</div>
						{/if}
					</div>

					<div class="flex-1 bg-gray-50">
						{#if pdfUrl}
							<iframe title="BKM PDF" src={pdfUrl} class="w-full h-full" />
						{:else}
							<div class="h-full flex items-center justify-center text-sm text-gray-500">
								选择某条文档链接后在此处预览
							</div>
						{/if}
					</div>
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>

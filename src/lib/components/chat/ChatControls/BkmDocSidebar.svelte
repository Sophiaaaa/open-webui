<script lang="ts">
	import { bkmDocSidebar } from '$lib/stores';

	function close() {
		bkmDocSidebar.set({ open: false, items: [] });
	}

	function formatPct(score?: number) {
		if (typeof score !== 'number' || Number.isNaN(score)) return '';
		return `${Math.round(score * 100)}%`;
	}

	function formatMeta(item: any) {
		const pdf = item?.pdf ?? '';
		const page = item?.page;
		if (!pdf) return '';
		return page ? `${pdf} · 第 ${page} 页` : `${pdf}`;
	}
</script>

{#if $bkmDocSidebar.open}
	<div class="h-full flex flex-col">
		<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
			<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">搜索文档</div>
			<div class="flex items-center gap-2">
				<div class="text-xs text-gray-500 dark:text-gray-400">{$bkmDocSidebar.items.length} 条</div>
				<button
					type="button"
					aria-label="关闭"
					class="px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-900/60 text-gray-500 dark:text-gray-400"
					on:click={close}
				>
					×
				</button>
			</div>
		</div>

		<div class="flex-1 overflow-auto">
			{#if $bkmDocSidebar.items.length > 0}
				<div class="divide-y divide-gray-100 dark:divide-gray-800">
					{#each $bkmDocSidebar.items as item}
						<a
							class="block px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-900/60"
							href={item.href}
							target="_blank"
							rel="noreferrer"
						>
							<div class="flex items-center justify-between gap-3">
								<div class="text-xs text-gray-500 dark:text-gray-400 truncate">{formatMeta(item)}</div>
								<div class="shrink-0 text-xs text-gray-500 dark:text-gray-400">{formatPct(item.score)}</div>
							</div>
							<div class="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100 break-words">
								{item.title || item.pdf}
							</div>
							{#if item.snippet}
								<div class="mt-1 text-xs text-gray-600 dark:text-gray-400 line-clamp-3 break-words">
									{item.snippet}
								</div>
							{/if}
						</a>
					{/each}
				</div>
			{:else}
				<div class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">
					点击左侧某组原因/行动建议后，这里会显示对应的 PDF 页码链接。
				</div>
			{/if}
		</div>
	</div>
{/if}


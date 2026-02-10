<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { tick } from 'svelte';

	export let kpi: string;
	export let allowedCategories: string[] = []; // e.g. ['organization', 'tools']
	export let initialSelection: string[] = [];
	export let onSelect: (selection: string[]) => void;

	const dispatch = createEventDispatcher();

	let uiConfig: any = null;
	let dynamicValues: Record<string, string[]> = {};
	let loadingType: string | null = null;
	let openDropdown: string | null = null;
	let searchTerms: Record<string, string> = {};
	let selectedScopes: string[] = [];

	$: if (initialSelection?.length && selectedScopes.length === 0) {
		selectedScopes = [...initialSelection];
	}

	// UI State
	let visibleCategories: any[] = [];
    let dropdownContainer: HTMLElement;

	onMount(() => {
		(async () => {
			try {
				const res = await fetch('/bottun/config/init');
				if (res.ok) {
					uiConfig = await res.json();
					updateVisibleCategories();
				}
			} catch (e) {
				console.error(e);
			}
		})();

		document.addEventListener('click', handleClickOutside);
		return () => {
			document.removeEventListener('click', handleClickOutside);
		};
	});

	function handleClickOutside(event: MouseEvent) {
		if (dropdownContainer && !dropdownContainer.contains(event.target as Node)) {
			openDropdown = null;
		}
	}

	$: if (uiConfig && allowedCategories) {
		updateVisibleCategories();
	}

	function getAllowedScopesFromUIConfig(): string[] {
		const level2 = uiConfig?.kpi_levels?.level2_mapping;
		if (!level2 || !kpi) return [];
		for (const key of Object.keys(level2)) {
			const list = level2[key] || [];
			for (const item of list) {
				if (item?.value === kpi) {
					return item?.allowed_scopes ?? [];
				}
			}
		}
		return [];
	}

	function updateVisibleCategories() {
		if (!uiConfig) return;
		const allCats = uiConfig.scope_options?.categories || [];
		let allowed = (allowedCategories ?? []).filter(Boolean);
		if (allowed.length === 0) {
			allowed = getAllowedScopesFromUIConfig();
		}
		visibleCategories = allowed.length > 0 ? allCats.filter((cat: any) => allowed.includes(cat.value)) : allCats;
	}

	async function fetchValues(dimensionType: string) {
		if (openDropdown === dimensionType) {
			openDropdown = null;
			return;
		}
		openDropdown = dimensionType;

		if (dynamicValues[dimensionType]) return;

		loadingType = dimensionType;
		try {
			const res = await fetch('/bottun/config/dimension', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					kpi: kpi,
					dimension_type: dimensionType,
					current_selection: selectedScopes
				})
			});
			if (res.ok) {
				const data = await res.json();
				dynamicValues = { ...dynamicValues, [dimensionType]: data.values };
			}
		} catch (e) {
			console.error(e);
		} finally {
			loadingType = null;
		}
	}

	function toggleScope(category: string, value: string) {
		const scopeStr = `${category}:${value}`;
		if (selectedScopes.includes(scopeStr)) {
			selectedScopes = selectedScopes.filter((s) => s !== scopeStr);
		} else {
			selectedScopes = [...selectedScopes, scopeStr];
		}
	}

	function confirmSelection() {
		onSelect(selectedScopes);
	}
</script>

<!-- Template -->
<div class="mt-2 flex flex-col gap-3" bind:this={dropdownContainer}>
	<!-- Buttons -->
	<div class="flex gap-2 flex-wrap">
		{#each visibleCategories as item}
			<div class="relative">
				<button
					class="px-3 py-1 rounded-full text-sm transition-colors border flex items-center gap-1
                    {openDropdown === item.value
						? 'bg-blue-600 text-white border-blue-600'
						: selectedScopes.some((s) => s.startsWith(item.value + ':'))
							? 'bg-blue-50 text-blue-700 border-blue-200'
							: 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:border-blue-400'}"
					on:click|stopPropagation={() => fetchValues(item.value)}
				>
					{item.label}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						class="transition-transform {openDropdown === item.value ? 'rotate-180' : ''}"
						><path d="m6 9 6 6 6-6" /></svg
					>
				</button>

				{#if openDropdown === item.value}
					<div
						class="absolute top-full left-0 mt-1 w-56 bg-white dark:bg-gray-800 shadow-xl rounded-md border border-gray-200 dark:border-gray-700 z-50 p-2 max-h-80 overflow-y-auto"
                        on:click|stopPropagation
					>
						<!-- Search -->
						<div class="mb-2 px-1">
							<input
								type="text"
								placeholder={`搜索${item.label}...`}
								class="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded bg-transparent dark:text-white focus:outline-none focus:border-blue-500"
								bind:value={searchTerms[item.value]}
							/>
						</div>

						{#if loadingType === item.value}
							<div class="p-4 flex justify-center text-sm text-gray-500">Loading...</div>
						{:else if dynamicValues[item.value]?.length > 0}
							<div class="flex flex-col gap-1">
								{#each dynamicValues[item.value].filter((val) => !searchTerms[item.value] || val
											.toLowerCase()
											.includes(searchTerms[item.value].toLowerCase())) as val}
									{@const isSelected = selectedScopes.includes(`${item.value}:${val}`)}
									<button
										class="block w-full text-left px-3 py-2 text-sm rounded transition-colors
                                        {isSelected
											? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 font-medium'
											: 'hover:bg-blue-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200'}"
										on:click={() => toggleScope(item.value, val)}
									>
										<div class="flex justify-between">
											<span>{val}</span>
											{#if isSelected}<span>✓</span>{/if}
										</div>
									</button>
								{/each}
								{#if dynamicValues[item.value].filter((val) => !searchTerms[item.value] || val
											.toLowerCase()
											.includes(searchTerms[item.value].toLowerCase())).length === 0}
									<p class="text-xs text-gray-400 p-2 text-center">无匹配结果</p>
								{/if}
							</div>
						{:else}
							<p class="text-xs text-gray-400 p-3 text-center italic">暂无可用数据</p>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	</div>

	<!-- Selected Summary -->
	{#if selectedScopes.length > 0}
		<div
			class="flex flex-col gap-2 p-2 bg-blue-50 dark:bg-gray-800 rounded-lg border border-blue-100 dark:border-gray-700"
		>
			<div class="flex flex-wrap gap-1">
				{#each selectedScopes as s}
					<span
						class="px-2 py-0.5 bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-300 text-[10px] rounded border border-blue-200 dark:border-gray-600 flex items-center gap-1"
					>
						{s.split(':')[1]}
						<button
							on:click={() => toggleScope(s.split(':')[0], s.split(':')[1])}
							class="hover:text-red-500">×</button
						>
					</span>
				{/each}
			</div>
			<button
				on:click={confirmSelection}
				class="w-full py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm"
			>
				确认选择 ({selectedScopes.length})
			</button>
		</div>
	{/if}
</div>

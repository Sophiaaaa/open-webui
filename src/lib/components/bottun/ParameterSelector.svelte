<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { getDimensionValues } from '$lib/apis/bottun';

	export let missingParams: string[] = [];
	export let currentContext: any = {};
	export let uiConfig: any = {};
	export let missingScopeCategories: string[] = [];

	const dispatch = createEventDispatcher();

	let kpiLevel1 = 'employee'; // Default
	let timeInput = '';
	let scopeSelections: any = {};
	let scopeOptions: any = {};
	let loadingScope: string | null = null;
    let showScopeDropdown: string | null = null;
    let scopeSearchTerms: any = {};

	// Helper to check if a param is missing
	$: isMissingKpi = missingParams.includes('kpi');
	$: isMissingTime = missingParams.includes('time_range');
	$: isMissingScope = missingParams.includes('scope');

	// KPI Selection
	function selectKpi(kpiValue: string) {
		dispatch('update', { kpi: kpiValue });
	}

	// Time Selection
	function selectTime(type: string) {
		const now = new Date();
		const currentYear = now.getFullYear();
		const currentMonth = now.getMonth() + 1; // 1-12
		
		let val = '';
        
        // Fiscal Year Logic: Starts April 1st
        // If current month >= 4, FY Start is current year
        // If current month < 4, FY Start is previous year
        const fyStartYear = currentMonth >= 4 ? currentYear : currentYear - 1;
        const fyEndYear = fyStartYear + 1;

		if (type === 'fy') {
            // Full Fiscal Year: StartYear04 - EndYear03
			val = `${fyStartYear}04-${fyEndYear}03`;
		} else if (type === 'half') {
            // Half Fiscal Year
            // H1: April - September (04-09)
            // H2: October - March (10-03)
            
            // Determine which half we are in
            // If month is 4,5,6,7,8,9 -> H1
            // If month is 10,11,12,1,2,3 -> H2
            
            if (currentMonth >= 4 && currentMonth <= 9) {
                // Current is H1
                val = `${fyStartYear}04-${fyStartYear}09`;
            } else {
                // Current is H2
                // H2 spans across years: StartYear10 - EndYear03
                val = `${fyStartYear}10-${fyEndYear}03`;
            }
		}
		
        if (val) {
            dispatch('update', { time_range: val });
        }
	}

    function submitTimeInput() {
        if (timeInput) {
             dispatch('update', { time_range: timeInput });
        }
    }

	// Scope Selection
	async function loadScopeOptions(category: string, search: string = '') {
		if (!currentContext.kpi) return;
        
        loadingScope = category;
        const currentSelectionsList = Object.entries(scopeSelections)
            .map(([k, v]) => `${k}:${v}`);
        
        // Add current category to selection list to filter by itself if needed? No, backend handles exclusion
        
        const token = localStorage.getItem('token');
        if (!token) return;

		const res = await getDimensionValues(token, currentContext.kpi, category, currentSelectionsList);
		if (res && res.values) {
            // Filter by search locally or backend? Backend supports it but we didn't implement LIKE in DB service fully
            // Let's do client side filtering if backend returns all, or rely on backend
            // The DB service `get_unique_values` has a Limit 100.
			scopeOptions = { ...scopeOptions, [category]: res.values };
		}
        loadingScope = null;
	}

    function toggleScopeDropdown(category: string) {
        if (showScopeDropdown === category) {
            showScopeDropdown = null;
        } else {
            showScopeDropdown = category;
            loadScopeOptions(category);
        }
    }

    function selectScope(category: string, value: string) {
        // Multi-select logic? Requirement says "多选后“确认选择”写回" (Multi-select then confirm)
        // But for simplicity in this component, let's assume single select per click or build a list
        
        // Actually, let's support adding to a list
        // But wait, the context structure uses a list of strings "category:value"
        
        const item = `${category}:${value}`;
        const currentScopes = currentContext.scope || [];
        
        // Toggle
        let newScopes;
        if (currentScopes.includes(item)) {
            newScopes = currentScopes.filter((s: string) => s !== item);
        } else {
            newScopes = [...currentScopes, item];
        }
        
        // Update local context immediately for UI feedback?
        // Or dispatch immediately?
        // Requirement: "多选后“确认选择”写回" -> Batch update
        scopeSelections[category] = value; // Just for local state if needed
        
        // We dispatch the FULL scope list
        dispatch('update', { scope: newScopes, _partial: true }); // _partial flag to not trigger "finished" yet?
    }

    function confirmScope() {
        dispatch('update', { _confirm_scope: true });
    }
    
    // Close dropdown on outside click (simple version)
    function handleOutsideClick(event: MouseEvent) {
        // Implement if needed, or use a backdrop
    }
</script>

<div class="flex flex-col gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm">
	{#if isMissingKpi}
		<div class="flex flex-col gap-2">
			<div class="font-semibold text-gray-700">请选择指标类型:</div>
			<div class="flex gap-2 mb-2">
				{#each uiConfig.kpi_levels?.level1 || [] as l1}
					<button
						class="px-3 py-1 rounded-full border {kpiLevel1 === l1.value ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'}"
						on:click={() => (kpiLevel1 = l1.value)}
					>
						{l1.label}
					</button>
				{/each}
			</div>
			<div class="grid grid-cols-2 gap-2">
				{#each uiConfig.kpi_levels?.level2_mapping?.[kpiLevel1] || [] as kpi}
					<button
						class="p-2 text-left bg-white border rounded hover:bg-blue-50 hover:border-blue-300 transition-colors"
						on:click={() => selectKpi(kpi.value)}
					>
						{kpi.label}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	{#if isMissingTime}
		<div class="flex flex-col gap-2">
			<div class="font-semibold text-gray-700">请选择时间范围:</div>
			<div class="flex gap-2">
				<button class="px-3 py-1 bg-white border rounded hover:bg-gray-100" on:click={() => selectTime('fy')}>
					本财年 (FY)
				</button>
				<button class="px-3 py-1 bg-white border rounded hover:bg-gray-100" on:click={() => selectTime('half')}>
					本半期 (Half)
				</button>
			</div>
            <div class="flex gap-2">
                <input 
                    type="text" 
                    bind:value={timeInput} 
                    placeholder="输入范围 (e.g. 202501-202506)" 
                    class="flex-1 px-3 py-1 border rounded"
                    on:keydown={(e) => e.key === 'Enter' && submitTimeInput()}
                />
                <button class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700" on:click={submitTimeInput}>
                    确认
                </button>
            </div>
		</div>
	{/if}

	{#if isMissingScope}
		<div class="flex flex-col gap-2">
			<div class="font-semibold text-gray-700">请补充筛选条件 (可多选):</div>
            
            <!-- Show categories that are missing OR all allowed categories? -->
            <!-- Requirement: "缺范围：按 KPI 允许的类别展示" -->
            <!-- We should show the missing categories prioritized, or just all allowed -->
            
            {#each (missingScopeCategories.length > 0 ? missingScopeCategories : uiConfig.scope_options?.categories?.map((c: any) => c.value) || []) as catValue}
                {@const catLabel = uiConfig.scope_options?.categories?.find((c: any) => c.value === catValue)?.label || catValue}
                
                <div class="relative">
                    <button 
                        class="w-full flex justify-between items-center px-3 py-2 bg-white border rounded hover:bg-gray-50"
                        on:click={() => toggleScopeDropdown(catValue)}
                    >
                        <span>{catLabel}</span>
                        <span class="text-xs text-gray-500">▼</span>
                    </button>
                    
                    {#if showScopeDropdown === catValue}
                        <div class="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg max-h-60 overflow-y-auto p-2">
                            {#if loadingScope === catValue}
                                <div class="text-center py-2 text-gray-500">加载中...</div>
                            {:else}
                                <div class="flex flex-col gap-1">
                                    {#each scopeOptions[catValue] || [] as opt}
                                        {@const isSelected = (currentContext.scope || []).includes(`${catValue}:${opt}`)}
                                        <button 
                                            class="text-left px-2 py-1 rounded hover:bg-blue-50 flex justify-between items-center {isSelected ? 'bg-blue-50 text-blue-700' : ''}"
                                            on:click={() => selectScope(catValue, opt)}
                                        >
                                            <span>{opt}</span>
                                            {#if isSelected}<span>✓</span>{/if}
                                        </button>
                                    {/each}
                                    {#if (scopeOptions[catValue] || []).length === 0}
                                        <div class="text-center py-2 text-gray-400">无选项</div>
                                    {/if}
                                </div>
                            {/if}
                        </div>
                        
                        <!-- Backdrop to close -->
                        <div class="fixed inset-0 z-0 cursor-default" on:click={() => (showScopeDropdown = null)}></div>
                    {/if}
                </div>
            {/each}
            
            <div class="mt-2">
                <button 
                    class="w-full py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium"
                    on:click={confirmScope}
                >
                    确认选择 / 开始查询
                </button>
                <div class="text-xs text-center text-gray-400 mt-1">
                    或者直接在对话框输入“没有了”
                </div>
            </div>
		</div>
	{/if}
</div>

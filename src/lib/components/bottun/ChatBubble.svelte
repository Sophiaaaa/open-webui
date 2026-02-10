<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import ParameterSelector from './ParameterSelector.svelte';
    import { marked } from 'marked';
    
    export let message: any;
    export let isBot: boolean = false;
    export let uiConfig: any = {};
    
    const dispatch = createEventDispatcher();

	function formatTimeRange(raw: string): string {
		const s = (raw ?? '').trim();
		if (!s) return '';

		const fyHalfOrQuarter = s.match(
			/^FY\s*(\d{2}|\d{4})\s*(1H|2H|H1|H2|Q[1-4]|上半期|下半期)?$/i
		);
		if (fyHalfOrQuarter) {
			let fyEndYear = Number.parseInt(fyHalfOrQuarter[1], 10);
			if (fyEndYear < 100) fyEndYear = 2000 + fyEndYear;
			const fyStartYear = fyEndYear - 1;
			const tag = (fyHalfOrQuarter[2] ?? '').toUpperCase();
			if (tag === '1H' || tag === 'H1' || fyHalfOrQuarter[2] === '上半期') {
				return `${fyStartYear}04-${fyStartYear}09`;
			}
			if (tag === '2H' || tag === 'H2' || fyHalfOrQuarter[2] === '下半期') {
				return `${fyStartYear}10-${fyEndYear}03`;
			}
			if (tag.startsWith('Q')) {
				const q = Number.parseInt(tag.slice(1), 10);
				if (q === 1) return `${fyStartYear}04-${fyStartYear}06`;
				if (q === 2) return `${fyStartYear}07-${fyStartYear}09`;
				if (q === 3) return `${fyStartYear}10-${fyStartYear}12`;
				if (q === 4) return `${fyEndYear}01-${fyEndYear}03`;
			}
			return `${fyStartYear}04-${fyEndYear}03`;
		}

		if (/^20\d{4}-20\d{4}$/.test(s)) return s;
		if (/^20\d{4}$/.test(s)) return `${s}-${s}`;
		if (/^20\d{2}$/.test(s)) return `${s}01-${s}12`;
		return s;
	}
    
    function handleUpdate(event: CustomEvent) {
        dispatch('update', event.detail);
    }
</script>

<div class="flex w-full {isBot ? 'justify-start' : 'justify-end'} mb-4">
    <div class="max-w-[80%] p-4 rounded-lg {isBot ? 'bg-white border border-gray-200' : 'bg-blue-600 text-white'} shadow-sm relative">
        {#if message.content}
            <!-- Render HTML safely (marked returns string) -->
            <div class="markdown-body text-sm break-words">
                {@html marked.parse(message.content)}
            </div>
        {/if}
        
        {#if isBot && message.missingParams && message.missingParams.length > 0}
            <div class="mt-3">
                <ParameterSelector 
                    missingParams={message.missingParams} 
                    currentContext={message.context}
                    uiConfig={uiConfig}
                    missingScopeCategories={message.missingScopeCategories || []}
                    on:update={handleUpdate}
                />
            </div>
        {/if}
        
        {#if isBot && message.error}
             <div class="mt-2 text-xs text-red-500 pt-1">
                Error: {message.error}
             </div>
        {/if}

		{#if isBot && message.context}
			{#if message.context.kpi || message.context.time_range || (message.context.scope && message.context.scope.length > 0) || message.sql}
				<div class="context-footer mt-2">
					{#if message.context.kpi}
						<div>KPI：{message.context.kpi}</div>
					{/if}
					{#if message.context.time_range}
						<div>时间范围：{formatTimeRange(message.context.time_range)}</div>
					{/if}
					{#if message.context.scope && message.context.scope.length > 0}
						<div>筛选条件：{message.context.scope.join(', ')}</div>
					{/if}
					{#if message.sql}
						<details class="mt-1">
							<summary class="cursor-pointer">SQL</summary>
							<pre class="mt-1 p-2 bg-gray-50 rounded text-[10px] overflow-x-auto not-italic text-gray-500 font-mono">{message.sql}</pre>
						</details>
					{/if}
				</div>
			{/if}
		{/if}
    </div>
</div>

<style>
    :global(.markdown-body p) {
        margin-bottom: 0.5em;
    }
    :global(.markdown-body p:last-child) {
        margin-bottom: 0;
    }
    :global(.markdown-body img) {
        max-width: 100%;
        border-radius: 4px;
        margin-top: 0.5em;
    }
    :global(.markdown-body a) {
        color: inherit;
        text-decoration: underline;
    }
	.context-footer, :global(.markdown-body .context-footer) {
		font-size: 0.75rem;
		color: #9ca3af;
		font-style: italic;
	}
</style>

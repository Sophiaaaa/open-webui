<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	export let title = '';
	export let months: string[] = [];
	export let values: number[] = [];

	let container: HTMLDivElement;
	let chart: any;
	let resizeObserver: ResizeObserver | null = null;

	function buildOption() {
		return {
			title: title ? { text: title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
			tooltip: {
				trigger: 'axis',
				axisPointer: { type: 'shadow' }
			},
			grid: { left: 48, right: 24, top: title ? 56 : 24, bottom: 32 },
			xAxis: {
				type: 'category',
				data: months,
				axisLabel: { rotate: 0 }
			},
			yAxis: { type: 'value' },
			series: [{ type: 'bar', data: values, barMaxWidth: 28 }]
		};
	}

	onMount(async () => {
		if (typeof window === 'undefined') return;
		const echarts = await import('echarts');
		chart = echarts.init(container);
		chart.setOption(buildOption());

		resizeObserver = new ResizeObserver(() => {
			chart?.resize();
		});
		resizeObserver.observe(container);
	});

	$: if (chart) {
		chart.setOption(buildOption(), { notMerge: true, lazyUpdate: true });
	}

	onDestroy(() => {
		try {
			resizeObserver?.disconnect();
		} catch {}
		try {
			chart?.dispose();
		} catch {}
	});
</script>

<div class="mt-2 w-full">
	<div class="w-full h-80" bind:this={container}></div>
</div>

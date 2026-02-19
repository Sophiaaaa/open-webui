<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { fly } from 'svelte/transition';

	export let show = false;
	export let width = 360;
	export let onClose = () => {};

	let modalElement: HTMLDivElement | null = null;
	let mounted = false;

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && isTopModal()) {
			show = false;
		}
	};

	const isTopModal = () => {
		const modals = document.getElementsByClassName('modal');
		return modals.length && modals[modals.length - 1] === modalElement;
	};

	onMount(() => {
		mounted = true;
	});

	$: if (show && modalElement) {
		document.body.appendChild(modalElement);
		window.addEventListener('keydown', handleKeyDown);
	} else if (modalElement) {
		onClose();
		window.removeEventListener('keydown', handleKeyDown);
		if (document.body.contains(modalElement)) {
			document.body.removeChild(modalElement);
		}
	}

	onDestroy(() => {
		show = false;
		if (modalElement && document.body.contains(modalElement)) {
			document.body.removeChild(modalElement);
		}
	});
</script>

{#if show}
	<div
		bind:this={modalElement}
		class="modal fixed inset-0 z-999 flex justify-end bg-black/40"
		in:fly={{ x: 80, duration: 120 }}
		on:mousedown={() => {
			show = false;
		}}
	>
		<div
			class="h-screen max-h-[100dvh] bg-white dark:bg-gray-850 dark:text-gray-100 shadow-xl overflow-hidden"
			style="width: {width}px"
			on:mousedown={(e) => {
				e.stopPropagation();
			}}
		>
			<slot />
		</div>
	</div>
{/if}


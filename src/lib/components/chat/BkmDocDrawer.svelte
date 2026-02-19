<script lang="ts">
	import { bkmDocSidebar } from '$lib/stores';
	import SideDrawer from '$lib/components/common/SideDrawer.svelte';
	import BkmDocSidebar from '$lib/components/chat/ChatControls/BkmDocSidebar.svelte';

	function close() {
		bkmDocSidebar.set({ open: false, items: [] });
	}
</script>

<SideDrawer show={$bkmDocSidebar.open} width={360} onClose={() => close()}>
	<BkmDocSidebar />
</SideDrawer>


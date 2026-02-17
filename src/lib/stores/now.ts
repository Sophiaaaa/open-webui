import { readable } from 'svelte/store';

export const currentDate = readable(new Date(), (set) => {
	if (typeof window === 'undefined') {
		return () => {
			return;
		};
	}

	let timeoutId: number | undefined;

	const scheduleNextTick = () => {
		const now = new Date();
		const nextMidnight = new Date(now);
		nextMidnight.setHours(24, 0, 0, 0);
		const delayMs = Math.max(0, nextMidnight.getTime() - now.getTime());

		timeoutId = window.setTimeout(() => {
			set(new Date());
			scheduleNextTick();
		}, delayMs);
	};

	scheduleNextTick();

	return () => {
		if (timeoutId !== undefined) window.clearTimeout(timeoutId);
	};
});

import { useFrame, useThree } from "@react-three/fiber";
import { useEffect } from "react";

export type AdaptiveRenderManagerProps = {
	deps: unknown[];
	active: boolean;
	onInvalidate: (fn: () => void) => void;
};

const AdaptiveRenderManager = ({
	deps,
	active,
	onInvalidate,
}: AdaptiveRenderManagerProps) => {
	const { invalidate } = useThree();

	useEffect(() => {
		onInvalidate(invalidate);
	}, [invalidate, onInvalidate]);

	useEffect(() => {
		invalidate();
	}, [invalidate, deps]);

	useFrame(() => {
		if (active) invalidate();
	});

	return null;
};

export default AdaptiveRenderManager;

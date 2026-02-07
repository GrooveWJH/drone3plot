export type TransformMode = "translate" | "rotate";

export type WaypointData = {
	id: string;
	position: [number, number, number];
	rotation: [number, number, number];
	takePhoto?: boolean;
};

export type PointCloudStats = {
	totalPoints: number;
	loadedPoints: number;
	sampleEvery: number;
	budgetMB: number;
};

export type LasHeaderInfo = {
	version: string;
	versionMajor: number;
	versionMinor: number;
	headerSize: number;
	offsetToPointData: number;
	pointCount: number;
	pointFormat: number;
	recordLength: number;
	scale: [number, number, number];
	offset: [number, number, number];
};

export type TrajectoryWaypoint = {
	x: number;
	y: number;
	z: number;
	yaw: number;
	takePhoto: boolean;
};

export type TrajectoryFile = {
	name: string;
	createdAt?: string;
	cloudTransform?: {
		fileName: string;
		rotation: [number, number, number];
		offset: [number, number, number];
	};
	waypoints: TrajectoryWaypoint[];
};

export type TrajectoryMeta = {
	id: string;
	label: string;
	source: "built-in" | "local";
	url?: string;
};

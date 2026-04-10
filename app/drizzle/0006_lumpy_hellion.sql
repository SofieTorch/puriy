PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_recordings` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`server_id` integer,
	`status` text NOT NULL,
	`line_id` text,
	`line_name` text,
	`is_detour` integer DEFAULT false,
	`detour_reason` text,
	`detour_description` text,
	`direction` text,
	`device_model` text,
	`os_version` text,
	`notes` text,
	`started_at` text NOT NULL,
	`ended_at` text,
	`last_activity_at` text NOT NULL,
	`synced_at` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
INSERT INTO `__new_recordings`("id", "server_id", "status", "line_id", "line_name", "is_detour", "detour_reason", "detour_description", "direction", "device_model", "os_version", "notes", "started_at", "ended_at", "last_activity_at", "synced_at", "created_at") SELECT "id", "server_id", "status", "line_id", "line_name", "is_detour", "detour_reason", "detour_description", "direction", "device_model", "os_version", "notes", "started_at", "ended_at", "last_activity_at", "synced_at", "created_at" FROM `recordings`;--> statement-breakpoint
DROP TABLE `recordings`;--> statement-breakpoint
ALTER TABLE `__new_recordings` RENAME TO `recordings`;--> statement-breakpoint
PRAGMA foreign_keys=ON;
PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_lines` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`status` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`cached_at` text NOT NULL
);
--> statement-breakpoint
INSERT INTO `__new_lines`("id", "name", "description", "status", "created_at", "updated_at", "cached_at") SELECT "id", "name", "description", "status", "created_at", "updated_at", "cached_at" FROM `lines`;--> statement-breakpoint
DROP TABLE `lines`;--> statement-breakpoint
ALTER TABLE `__new_lines` RENAME TO `lines`;--> statement-breakpoint
PRAGMA foreign_keys=ON;
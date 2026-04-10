CREATE TABLE `saved_trips` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`origin_name` text NOT NULL,
	`dest_name` text NOT NULL,
	`origin_lon` real NOT NULL,
	`origin_lat` real NOT NULL,
	`dest_lon` real NOT NULL,
	`dest_lat` real NOT NULL,
	`type` text NOT NULL,
	`route_json` text NOT NULL,
	`created_at` text DEFAULT (datetime('now')) NOT NULL
);

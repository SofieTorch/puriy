ALTER TABLE `recordings` ADD `is_detour` integer DEFAULT false;--> statement-breakpoint
ALTER TABLE `recordings` ADD `detour_reason` text;--> statement-breakpoint
ALTER TABLE `recordings` ADD `detour_description` text;
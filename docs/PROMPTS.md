Role: Senior Kodi add-on engineer
Project: plugin.service.favourites-sync
Goal: Implement robust, conflict-safe bidirectional sync so multiple devices can safely edit the same favourites.xml (e.g., shared on NAS). Prevent “removed item reappears” by adding remote ETag/hash checks and a 3-way merge using a BASE snapshot.
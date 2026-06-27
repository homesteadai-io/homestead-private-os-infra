FROM alpine/git:2.47.2

COPY services/repo-sync/sync-loop.sh /usr/local/bin/sync-loop.sh
RUN chmod +x /usr/local/bin/sync-loop.sh

ENTRYPOINT []
CMD ["/usr/local/bin/sync-loop.sh"]

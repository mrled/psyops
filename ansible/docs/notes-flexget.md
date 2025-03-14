# Flexget notes

Played with flexget a bit.
Don't need it right now.
Could be useful in the future for piping torrent RSS feeds to transmission.

## Example compose entry

This worked for me

```
  flexget:
    image: cpoppema/docker-flexget
    environment:
      PUID: "{{ seedbox_uid }}"
      PGID: "{{ seedbox_gid }}"
      TZ: "{{ seedbox_timezone }}"
      TORRENT_PLUGIN: transmission
      FLEXGET_LOG_LEVEL: debug
      WEB_PASSWD: "{{ seedbox_web_admin_pass }}"
    volumes:
      - "{{ seedbox_flexget_config_dir }}:/config"
      - "{{ seedbox_media_dir }}:/media"
    networks:
      - dernetverk
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.seedbox-flexget.rule=Host(`{{ seedbox_domain }}`) && PathPrefix(`/flexget`)"
      - "traefik.http.routers.seedbox-flexget.tls=true"
      - "traefik.http.routers.seedbox-flexget.tls.certresolver=seedbox-resolver"
      - "traefik.http.routers.seedbox-flexget.service=seedbox-flexget"
      - "traefik.http.services.seedbox-flexget.loadbalancer.server.port=5050"
      - "traefik.http.routers.seedbox-flexget.middlewares=seedbox-auth"
```

## Example config

I got this off of a website

```
presets:

  output_trans:
    transmission:
      host: localhost
      port: 9091
      addpaused: no

  send_email:
    email:
      template: accepted
      from: username@gmail.com
      to:   username@gmail.com
      smtp_host: smtp.gmail.com
      smtp_port: 587
      smtp_username: username@gmail.com
      smtp_password: PASSWORDHERE
      smtp_tls: yes

  generate_rss:
    make_rss: /tank/media/html/downloaded.rss

  movies:
    set:
      path: /tank/media/movies
    quality: 720p hdtv+
    imdb_required: yes
    exists_movie:
      - /tank/media/archive
      - /tank/media/movies
    imdb:
      min_score: 7.0
      min_votes: 5000
      min_year: 2012
      reject_genres:
        - horror


  tv:
    set:
      path: /tank/media/tv/{{series_name}}/{{series_season}}
    exists_series:
      path: /tank/media/tv
      allow_different_qualities: better

    series:
      settings:
        720p:
          propers: yes
          timeframe: 4 hours
          target: 720p hdtv !webdl
        hdtv:
          propers: yes
          target: hdtv <=720p !webdl
          timeframe: 24 hours
          quality: <=720p hdtv !webdl

      720p:
        - the colbert report:
            timeframe: 1 hour
        - the daily show:
            timeframe: 1 hour
        - real time with bill maher:
            quality: <=hdtv
        - archer 2009
        - orphan black
        - castle 2009
        - community
        - david attenboroughs africa
        - dual survival
        - fifth gear
        - game of thrones
        - justified
        - mad men
        - modern family
        - robot chicken
        - suits
        - the big bang theory
        - the walking dead
        - top gear:
            name_regexp: ^top.gear(?!.us)
        - how i met your mother
        #- doctor who 2005

tasks:

  othersite_tv:
    priority: 1
    rss: http://some.other.example.org/feed.rss
    manipulate:
      - title:
          extract: (?<=file\:\ )(.*)(?= thread)(?=.*)
    preset:
      - tv
      - output_trans
      - send_email
      - generate_rss

  othersite_movies:
    priority: 2
    rss: http://some.other.example.org/feed2.rss
    manipulate:
      - title:
          extract: (?<=file\:\ )(.*)(?= thread)(?=.*)
    preset:
      - movies
      - output_trans
      - send_email
      - generate_rss

  onesite_tv:
    priority: 4
    rss: { url: 'https://onesite.example.net/d/rss.php?f=22', username: 'Jack', password: 'MYPASSWORD' }
    preset:
      - tv
      - output_trans
      - send_email
      - generate_rss

  onesite_movies:
    priority: 5
    rss: { url: 'https://onesite.example.net/d/rss.php?f=7', username: 'Jack', password: 'HASHPASSWORD' }
    preset:
      - movies
      - output_trans
      - send_email
      - generate_rss


```

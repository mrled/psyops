#!/usr/bin/python3


class FilterModule(object):

    def filters(self):
        return {
            'dictlist_combine_uniqkey': self.dictlist_combine_uniqkey,
            'dictlist_with_defaults': self.dictlist_with_defaults,
        }

    def dictlist_combine_uniqkey(self, lista, listb, key):
        """Combine two lists of dicts using a unique key.

        Create a new list from two input lists where each element in the list is a dict.
        Use one element in each dict as the identifier.
        If a dict with the same identifier exists in both lists,
        the dict in the second list replaces the dict in the first.
        Otherwise, the dicts are appended.

        Usage:

        list1 | dictlist_combine_uniqkey(list2, key)

        Example:

        list1:
        - src: /tmp/felix
          dest: /etc/felix
        - src: /var/tmp/francis
          dest: /etc/francis

        list2:
        - src: /home/clou/felix
          dest: /etc/felix
        - src: /home/clou/billiam
          dest: /etc/billiam

        ---
        - name: combine two lists using a unique key
          set_fact:
            copylist: {{ dictlist_combine_uniqkey: list1 | dictlist_combine_uniqkey(list2, 'dest') }}
        ---

        Example result:

        copylist:
        - src: /home/clou/felix
          dest: /etc/felix
        - src: /var/tmp/francis
          dest: /etc/francis
        - src: /home/clou/billiam
          dest: /etc/billiam
        """
        result = {}
        lista = lista if isinstance(lista, list) else [lista]
        listb = listb if isinstance(listb, list) else [listb]
        listb_uniqkeys = [bitem[key] for bitem in listb]
        result = [aitem for aitem in lista if aitem[key] not in listb_uniqkeys]
        result += listb
        return result

    def dictlist_with_defaults(self, dictlist, defaults):
        """For each dict in a list, provide a set of defaults, and return a new dict list.

        Given a list of dicts and a default dict,
        return a new list with the defaults filled in for any key not provided.

        Usage:

        dictlist | dictlist_with_defaults(defaults)

        Example:

        initial_dictlist:
        - name: slappy
          mode: overdrive
          lock: false
        - name: mappy
          lights: on

        default_dict:
          name: ""
          mode: normal
          lock: true
          lights: off

        ---
        - name: Apply defaults to a dictlist
          set_fact:
            final_dictlist: "{{ initial_dictlist | dictlist_with_defaults(default_dict) }}
        ---

        Example result:

        final_dictlist:
        - name: slappy
          mode: overdrive
          lock: false
          lights: off
        - name: mappy
          lights: on
          mode: overdrive
          lock: false
        """
        return [{**defaults, **dictlist_item} for dictlist_item in dictlist]

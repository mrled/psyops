from progfiguration.inventory.invhelpers import Bunch

node = Bunch(
    notes = '',
    motd = Bunch(
        flavor = "A war is being fought here between taxidermied animals and abandoned theme park animatronics, yet all we can perceive is stillness.",
    ),
    pubkey = 'age19ylpmjad3kl8lvhzt8djpeuq4y2cdw6wfy6zklf4zrdm7yuv9vfs49qmvg',
    # groups = [
    #     "kubernasty",
    # ],
    roles = Bunch(
        skunkworks = {},
        k3s = {
            'start_k3s': False,
        },
    ),
    serial = "",
)

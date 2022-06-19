from progfiguration.inventory.invhelpers import Bunch

node = Bunch(
    notes = '',
    motd = Bunch(
        flavor = "An endless shopping mall with an equally endless arcade of black neon, whose only available game is a rehearsal of thermonuclear war.",
    ),
    pubkey = 'age1y2q4ftlq087sxetvm2uv8rqftn9x2maqsrhuyyf6zzjvfhr37afq56kwpk',
    # groups = [
    #     "kubernasty",
    # ],
    roles = Bunch(
        skunkworks = {},
        k3s = {
            'start_k3s': False,
        },
    ),
    serial = "10K7GQ2",
)

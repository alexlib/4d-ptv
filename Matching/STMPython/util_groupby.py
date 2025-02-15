import itertools

import numpy as np

from transonic import boost
from time import perf_counter


@boost
def special_argsort(cells: "int32[:,:]"):

    max_index = cells.max()
    if max_index > 1024:
        raise ValueError

    multiplicator = 2
    while multiplicator < max_index:
        multiplicator *= 2

    cells = np.array(cells, dtype=np.int32)

    cells_as_ints = (
        multiplicator ** 2 * cells[:, 0]
        + multiplicator * cells[:, 1]
        + cells[:, 2]
    )

    del cells

    indices = cells_as_ints.argsort()

    cells_as_ints_sorted = cells_as_ints[indices]

    return indices, np.array(np.diff(cells_as_ints_sorted), dtype=bool)


def group_by_cam(group):
    nb_elems = group.shape[0]
    assert nb_elems >= 3

    elems = list(tuple(group[index, :]) for index in range(group.shape[0]))

    # no supported by Pythran
    # elems.sort(key=lambda elem: elem[0])
    # replaced by:
    cam_id_array = np.array([group[index, 0] for index in range(group.shape[0])])
    indices = cam_id_array.argsort()
    elems = [elems[index] for index in indices]

    result = []
    elem = elems[0]
    cam_id_old = elem[0]
    subgroup = [elem]

    for elem in elems[1:]:
        cam_id = elem[0]
        if cam_id != cam_id_old:
            result.append(subgroup)
            cam_id_old = cam_id
            subgroup = [elem]
        else:
            subgroup.append(elem)

    if subgroup != result[-1]:
        result.append(subgroup)

    return result


@boost
def kernel_make_groups_by_cell_cam(
    cam_ray_ids_sorted: "int32[:, :]", diffs: "bool[:]", cam_match: int
):
    groups = []
    candidates = []
    start_group = 0
    for index, diff in enumerate(diffs):
        if diff:
            # we exit a group
            stop_group = index + 1
            nb_elems = stop_group - start_group
            if nb_elems >= cam_match:
                group = cam_ray_ids_sorted[start_group:stop_group, :]
                cam_ids = group[:, 0]
                nb_cameras = len(set(cam_ids))
                if nb_cameras >= cam_match:
                    if nb_elems == 2:
                        # we can already compute the candidate
                        tup0 = tuple(group[0])
                        tup1 = tuple(group[1])
                        # we'd like to have (not supported by Pythran)
                        # if tup1 > tup0:
                        #     cand = (tup0, tup1)
                        # else:
                        #     cand = (tup1, tup0)
                        # it could also be written as (not supported by Pythran)
                        # cand = sorted((tup0, tup1))
                        # Pythran supports
                        # (buggy, then we need the list comp. at the end)
                        cand = (tup0, tup1)
                        candidates.append(cand)
                    else:
                        groups_cam = group_by_cam(group)
                        assert len(groups_cam) == nb_cameras
                        if nb_cameras == 2:
                            # we can already compute candidates
                            candidates.extend(
                                [
                                    # not supported by Pythran
                                    # tuple(sorted(tup))
                                    tup
                                    for tup in itertools.product(
                                        groups_cam[0], groups_cam[1]
                                    )
                                ]
                            )
                        # it would be good for performance to do the same
                        # with 3 cameras (no supported by Pythran?)
                        # elif nb_cameras == 3:
                        #     candidates.extend(
                        #         [
                        #             tup
                        #             for tup in itertools.product(
                        #                 groups_cam[0],
                        #                 groups_cam[1],
                        #                 groups_cam[2],
                        #             )
                        #         ]
                        #     )
                        else:
                            groups.append(groups_cam)
            start_group = stop_group

    # needed because we can't add sorted tuples above (Pythran limitation)
    candidates = [tuple(sorted(cand)) for cand in candidates]
    candidates = list(set(candidates))
    return groups, candidates


def make_groups_by_cell_cam(cells_all, cam_ray_ids, cam_match: int):
    """

    Inputs
    ------

    traversed:

      Sequence[(cam_id, ray_id, cell)]


    Returns
    -------

    Sequence[Sequence[(cam_id, ray_id)]]

    Set[Tuple[(cam_id, ray_id)]]

    We'd like to filter out groups with less than ``cam_match`` cameras.

    """
    t_start = perf_counter()
    indices, diffs = special_argsort(cells_all)
    del cells_all
    cam_ray_ids_sorted = cam_ray_ids[indices, :]
    groups, candidates = kernel_make_groups_by_cell_cam(
        cam_ray_ids_sorted, diffs, cam_match
    )
    print(f"make_groups_by_cell_cam done in {perf_counter() - t_start:.2f} s")
    return groups, candidates

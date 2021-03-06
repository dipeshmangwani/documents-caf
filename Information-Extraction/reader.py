import xml.etree.ElementTree
import os
import json
import argparse
import re
import numpy as np
import pickle


class Reader(object):
    def __init__(self, params=None):
        self.params = params

    def get_attribs(self, items):
        obj = {}
        for item in items:
            obj[item[0]] = item[1]
        return obj

    def is_y_similar(self, ry0, ry1, y0, y1):
        if ry0 == y0:
            return True
        if ry0 < y0 < ry1:
            return True
        return False

    def get_page_text(self, tree, dims):
        width = dims[0]
        height = dims[1]
        text_boxes = tree.findall("textbox")
        text = []
        tb = {}
        lines = []
        line_num = 0
        for box in text_boxes:
            box_id = box.attrib["id"]
            box_coords = box.attrib["bbox"].split(",")
            box_coords = [float(b) for b in box_coords]
            tb[box_id] = box_coords
            for line in box:
                if line.tag == "textline":
                    line_coords = line.attrib["bbox"].split(",")
                    line_coords = [float(b) for b in line_coords]
                    words = []
                    for child in line:
                        if child.tag == "text":
                            words.append(child.text)
                    words = ''.join(words)
                    words = words.rstrip().lstrip()
                    if len(words) > 0:
                        line_coords.append(box_id)
                        line_coords.append(line_num)
                        line_coords.append(words)
                        lines.append(line_coords)
                        text.append(words)
                        line_num += 1
        figure_boxes = tree.findall("figure")
        fig_words = []
        unique_y = {}
        for box in figure_boxes:
            for item in box:
                if item.tag == "text":
                    word_coords = item.attrib["bbox"].split(",")
                    word_coords = [float(b) for b in word_coords]
                    unique_y[(word_coords[1], word_coords[3])] = True
                    word_coords.append(item.text)
                    fig_words.append(word_coords)
        fig_words = sorted(fig_words, key=lambda x: (-x[1], x[0]))
        fig_line = []
        fig_inds = []
        for y in unique_y.keys():
            ref_y0 = y[0]
            ref_y1 = y[1]
            W = []
            tmp_inds = []
            for idx, w in enumerate(fig_words):
                if idx not in fig_inds:
                    y0 = w[1]
                    y1 = w[3]
                    if self.is_y_similar(ref_y0, ref_y1, y0, y1):
                        W.append(w)
                        tmp_inds.append(idx)
            W = sorted(W, key=lambda x: (-x[1], x[0]))
            tmp_inds = list(set(tmp_inds))
            fig_inds.extend(tmp_inds)
            widths = []
            for i, ww in enumerate(W):
                widths.append(ww[2] - ww[0])
            med = np.mean(widths) if len(widths) > 0 else 0.
            line = []
            for i, ww in enumerate(W):
                if i == 0:
                    line.append(ww)
                else:
                    g = ww[0] - W[i - 1][2]
                    if g > 4. * med:
                        chars = []
                        for l in line:
                            chars.append(l[-1])
                        if len(chars) > 0:
                            bb = [line[0][0], line[0][1], line[-1][2], line[-1][3], line_num, line_num, "".join(chars)]
                            fig_line.append(bb)
                        line = [ww]
                    else:
                        line.append(ww)
            chars = []
            for l in line:
                chars.append(l[-1])
            if len(chars) > 0:
                bb = [line[0][0], line[0][1], line[-1][2], line[-1][3], line_num, line_num, "".join(chars)]
                fig_line.append(bb)
            line_num += 1
            unique_y[y] = W

        lines.extend(fig_line)
        groups = {}
        indices = []
        lines = sorted(lines, key=lambda x: (-x[1], x[0]))
        # groups = []
        for line in lines:
            idx = line[-2]
            if idx not in indices:
                tmp = [idx]
                ref_y0 = line[1]
                ref_y1 = line[3]
                for line2 in lines:
                    idx2 = line2[-2]
                    if (idx2 not in indices) and (idx != idx2):
                        y0 = line2[1]
                        y1 = line2[3]
                        x = line2[0]
                        if self.is_y_similar(ref_y0, ref_y1, y0, y1):
                            tmp.append(idx2)
                tmp = list(set(tmp))
                tmp_lines = [line for line in lines if line[-2] in tmp]
                tmp_lines = sorted(tmp_lines, key=lambda x: (-x[1], x[0]))
                if len(tmp_lines) > 0:
                    groups[tmp_lines[0][-2]] = tmp_lines
                indices.extend(tmp)
                indices = list(set(indices))
        new_groups = {}
        block_types = {}
        indices = []
        block_type = 0
        keys = sorted(groups, key=lambda k: len(groups[k]), reverse=True)
        for k in keys:
            inds = []
            items = groups[k]
            if len(items) < 2:
                block_type = 0
            elif len(items) > 2:
                block_type = 2
            else:
                block_type = 1
            for item in items:
                idx = item[-2]
                h = np.abs(item[1] - item[3])
                if idx not in indices:
                    indices.append(idx)
                    inds.append(idx)
                    box_id = int(item[-3])
                    for line in lines:
                        idx2 = line[-2]
                        box2_id = int(line[-3])
                        if idx2 not in indices:
                            if box2_id == box_id:
                                if idx2 in groups:
                                    items2 = groups[idx2]
                                    if len(items2) < 2:
                                        for tmp in items2:
                                            yy = np.abs(tmp[3] - item[1])
                                            if yy > h:
                                                pass
                                            else:
                                                inds.append(tmp[-2])
                                                indices.append(tmp[-2])
            inds = list(set(inds))
            tmp_lines = [line for line in lines if line[-2] in inds]
            tmp_lines = sorted(tmp_lines, key=lambda x: (-x[1], x[0]))
            if len(tmp_lines) > 0:
                new_groups[tmp_lines[0][-2]] = tmp_lines
                block_types[tmp_lines[0][-2]] = block_type
            indices = list(set(indices))
        blocks = []
        key_values = []
        # multi_columns = []
        for k, v in new_groups.items():
            if block_types[k] != 1:
                tmp = []
                for item in v:
                    tmp.append(item[-1].rstrip().lstrip())
                text = " ".join(tmp)
                if len(text.rstrip().lstrip()) > 0:
                    text = re.sub("\s{2,}", "  ", text)
                    tmp = text.split("  ")
                    new_tmp = []
                    for tt in tmp:
                        ttt = tt.split(" ")
                        lts = [len(x) for x in ttt]
                        lts = list(set(lts))
                        if len(lts) == 1 and lts[0] == 1 and len(ttt) > 2:
                            new_tmp.append("".join(ttt))
                        else:
                            new_tmp.extend(ttt)
                    text = " ".join(new_tmp)
                    blocks.append([v[0][0], v[0][1], v[-1][2], v[-1][3], text])
            elif block_types[k] == 1:
                ref_item = v[0]
                ref_x = ref_item[2]
                K = [ref_item]
                V = []
                for item in v[1:]:
                    x = item[0]
                    if x > ref_x:
                        V.append(item)
                    else:
                        K.append(item)
                k_text = []
                v_text = []
                for kk in K:
                    k_text.append(kk[-1])
                for kk in V:
                    v_text.append(kk[-1])
                tmp_k = " ".join(k_text).split("/")
                tmp_v = " ".join(v_text).split("/")
                if len(tmp_k) == len(tmp_v):
                    for xx in range(len(tmp_k)):
                        key_values.append([tmp_k[xx], tmp_v[xx]])
                elif len(tmp_k) > 1 and len(tmp_v) == 1:
                    for xx in range(len(tmp_k)):
                        key_values.append([tmp_k[xx], tmp_v[0]])
                else:
                    key_values.append([" ".join(k_text), " ".join(v_text)])
        blocks = sorted(blocks, key=lambda x: (-x[1], x[0]))
        blocks = [b[-1] for b in blocks]

        return blocks, key_values

    def get_content(self):
        params = self.params
        if not os.path.exists(params["src"]):
            return
        tree = xml.etree.ElementTree.parse(params["src"])
        root = tree.getroot()
        page_ids = []
        page_dims = []
        for child in root:
            tag = child.tag
            if tag == 'page':
                obj = self.get_attribs(child.items())
                page_ids.append(obj['id'])
                bbox = obj["bbox"].split(",")[2:]
                bbox = [float(b) for b in bbox]
                page_dims.append(bbox)

        print('Number of Pages: ', len(page_ids))
        blocks = []
        key_values = []
        texts = []
        for i, id in enumerate(page_ids):
            page_text = []
            selector = "./page[@id=" + "'" + id + "']"
            page_tree = root.find(selector)
            page_blocks, kv = self.get_page_text(page_tree, page_dims[i])
            blocks.append(page_blocks)
            key_values.append(kv)
            page_text.append("\n".join(page_blocks))
            page_text.extend([" ".join(items) for items in kv])
            page_text = "\n".join(page_text)
            texts.append(page_text)
        return blocks, key_values, texts


if __name__ == '__main__':
    flags = argparse.ArgumentParser("Command line arguments for Document Processing")
    flags.add_argument("-src", type=str, required=True, help="Source file path")
    args = flags.parse_args()
    params = vars(args)
    try:
        reader = Reader(params)
        blocks, kv, text = reader.get_content()
        data = {"text": text, "blocks": blocks, "kv": kv}
        with open("tmp.pkl", "wb") as fi:
            pickle.dump(data, fi)
    except Exception as e:
        print(str(e))

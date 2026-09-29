(* Mechanized core of SchemaCaps: the non-amplification guarantee.
   Verified with Coq. It formalizes exactly the assumptions stated in the paper:
   authority coordinates are a fixed set (Idx), a schema's authority is the set of value-tuples it
   admits on those coordinates, a step is non-amplifying when every marginal shrinks, and the
   product condition lets the per-coordinate (marginal) check imply the joint inclusion the
   proposition needs. Nothing about server behaviour is claimed: [Auth] is the schema-visible
   authority set, by construction. *)

Require Import Coq.Setoids.Setoid.

Section NonAmplification.

Variable Idx : Type.          (* authority-bearing coordinates, incl. the undeclared-field marker star; FIXED across versions *)
Variable Val : Type.          (* values, incl. a distinguished "absent"/bottom element *)

Definition Tuple := Idx -> Val.
Definition ASet  := Tuple -> Prop.               (* a schema's schema-visible authority set *)

Definition subset (X Y : ASet) := forall t, X t -> Y t.
Notation "X [= Y" := (subset X Y) (at level 70).

(* marginal of X on coordinate i: the values i can take in some admitted tuple *)
Definition marg (X : ASet) (i : Idx) (v : Val) := exists t, X t /\ t i = v.

(* X is a product of its marginals: any tuple whose every coordinate is individually admissible is admitted. *)
Definition is_product (X : ASet) := forall t, (forall i, marg X i (t i)) -> X t.

(* --- Lemma 1 (product condition): per-coordinate inclusion => joint inclusion, when the OLD set is a product. *)
Lemma marginal_implies_joint :
  forall Xold Xnew : ASet,
    is_product Xold ->
    (forall i v, marg Xnew i v -> marg Xold i v) ->   (* every new marginal is included in the old one *)
    Xnew [= Xold.
Proof.
  intros Xold Xnew Hprod Hmarg t Ht.
  apply Hprod. intro i.
  apply Hmarg. exists t. split; [exact Ht | reflexivity].
Qed.

(* subset is a preorder *)
Lemma subset_refl : forall X, X [= X. Proof. intros X t H; exact H. Qed.
Lemma subset_trans : forall X Y Z, X [= Y -> Y [= Z -> X [= Z.
Proof. intros X Y Z Hxy Hyz t Ht; apply Hyz, Hxy, Ht. Qed.

(* --- A chain of versions X 0 .. X n, each re-bound silently: every step non-amplifying (joint). *)
Variable X : nat -> ASet.
Hypothesis step_nonamp : forall k, X (S k) [= X k.

Lemma chain_nonamp : forall n, X n [= X 0.
Proof.
  induction n as [| n IH].
  - apply subset_refl.
  - apply subset_trans with (Y := X n); [ apply step_nonamp | exact IH ].
Qed.

(* --- Proposition 1: with a policy P over the same fixed coordinates, authorised calls after n
       silent re-bindings reach no authority tuple unreachable under the original grant. *)
Variable P : ASet.
Definition Auth (k : nat) : ASet := fun t => X k t /\ P t.

Theorem no_amplification_along_chain : forall n, Auth n [= Auth 0.
Proof.
  intros n t Ht. destruct Ht as [Hx Hp]. split.
  - exact (chain_nonamp n t Hx).
  - exact Hp.
Qed.

(* --- Corollary (effective authority under fidelity): if the server's real effect B never exceeds what
       the schema-visible authority tuple permits (fidelity), the guarantee carries to effects.
       Fidelity is an ASSUMPTION, made explicit here, not proved -- this is the boundary of the result. *)
Variable Effect : Type.
Variable B : Tuple -> Effect -> Prop.            (* B t e : the server may produce effect e on an admitted call t *)
Variable permitted0 : Effect -> Prop.            (* effects reachable under the original grant *)
Hypothesis fidelity : forall t e, Auth 0 t -> B t e -> permitted0 e.

Theorem effect_no_amplification :
  forall n t e, Auth n t -> B t e -> permitted0 e.
Proof.
  intros n t e Ht He.
  exact (fidelity t e (no_amplification_along_chain n t Ht) He).
Qed.


(* --- Chain from the ACTUAL checks: per-coordinate inclusion + product condition at each step.
       This is what the rule verifies; the joint step is derived (Lemma 1), not assumed. *)
Section MarginalChain.
Variable Y : nat -> ASet.
Hypothesis Yprod : forall k, is_product (Y k).                    (* product condition on each old schema *)
Hypothesis Ystep : forall k i v, marg (Y (S k)) i v -> marg (Y k) i v.   (* every new marginal <= old marginal *)

Lemma joint_step : forall k, Y (S k) [= Y k.
Proof.
  intro k. apply (marginal_implies_joint (Y k) (Y (S k)) (Yprod k)). intros i v. apply Ystep.
Qed.

Theorem marginal_chain_nonamp : forall n, Y n [= Y 0.
Proof.
  induction n as [| n IH].
  - apply subset_refl.
  - apply subset_trans with (Y := Y n); [ apply joint_step | exact IH ].
Qed.

Variable Q : ASet.
Definition AuthY (k : nat) : ASet := fun t => Y k t /\ Q t.
Theorem marginal_no_amplification : forall n, AuthY n [= AuthY 0.
Proof.
  intros n t Ht. destruct Ht as [Hy Hq]. split.
  - exact (marginal_chain_nonamp n t Hy).
  - exact Hq.
Qed.
End MarginalChain.

End NonAmplification.

Print Assumptions no_amplification_along_chain.
Print Assumptions marginal_no_amplification.
Print Assumptions effect_no_amplification.
